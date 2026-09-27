"""GitHub 代码提交采集模块。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from shared.logger import get_logger

logger = get_logger("collector.github")

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_PER_PAGE = 30
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_INTERVAL = 5.0
DEFAULT_RATE_LIMIT_RETRIES = 3


@dataclass(frozen=True)
class CommitRecord:
    author: str
    message: str
    timestamp: datetime
    repo: str
    additions: int
    deletions: int
    files_changed: int


def collect(
    repos: list[str],
    since: datetime,
    until: datetime,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_interval: float = DEFAULT_RETRY_INTERVAL,
    rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[CommitRecord]:
    """采集指定仓库在时间窗口内的 commit 记录。

    超时重试 max_retries 次（间隔 retry_interval 秒）；仍失败返回空列表并记错误日志。
    遇到 HTTP 403 限流时，等待 X-RateLimit-Reset / Retry-After 后重试。
    """
    if not repos:
        return []

    auth_token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "daily-report-collector",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    owns_client = client is None
    http_client = client or httpx.Client(base_url=GITHUB_API_BASE, headers=headers, timeout=timeout)

    try:
        records: list[CommitRecord] = []
        for repo in repos:
            repo_records = _collect_repo(
                client=http_client,
                repo=repo,
                since=since,
                until=until,
                max_retries=max_retries,
                retry_interval=retry_interval,
                rate_limit_retries=rate_limit_retries,
                sleep_fn=sleep_fn,
            )
            records.extend(repo_records)
        return records
    finally:
        if owns_client:
            http_client.close()


def _collect_repo(
    *,
    client: httpx.Client,
    repo: str,
    since: datetime,
    until: datetime,
    max_retries: int,
    retry_interval: float,
    rate_limit_retries: int,
    sleep_fn: Callable[[float], None],
) -> list[CommitRecord]:
    try:
        commit_summaries = _list_commits(
            client=client,
            repo=repo,
            since=since,
            until=until,
            max_retries=max_retries,
            retry_interval=retry_interval,
            rate_limit_retries=rate_limit_retries,
            sleep_fn=sleep_fn,
        )
    except _CollectFailed as exc:
        logger.error(
            "GitHub 采集失败，返回空列表",
            extra={"repo": repo, "error": str(exc)},
        )
        return []

    records: list[CommitRecord] = []
    for summary in commit_summaries:
        sha = summary.get("sha")
        if not sha:
            continue
        try:
            detail = _get_commit_detail(
                client=client,
                repo=repo,
                sha=sha,
                max_retries=max_retries,
                retry_interval=retry_interval,
                rate_limit_retries=rate_limit_retries,
                sleep_fn=sleep_fn,
            )
        except _CollectFailed as exc:
            logger.error(
                "GitHub 采集失败，返回空列表",
                extra={"repo": repo, "sha": sha, "error": str(exc)},
            )
            return []

        record = _to_commit_record(repo=repo, summary=summary, detail=detail)
        if record is not None:
            records.append(record)
    return records


class _CollectFailed(Exception):
    """内部：重试耗尽后的采集失败。"""


def _list_commits(
    *,
    client: httpx.Client,
    repo: str,
    since: datetime,
    until: datetime,
    max_retries: int,
    retry_interval: float,
    rate_limit_retries: int,
    sleep_fn: Callable[[float], None],
) -> list[dict[str, Any]]:
    page = 1
    all_commits: list[dict[str, Any]] = []

    while True:
        params = {
            "since": _to_iso(since),
            "until": _to_iso(until),
            "per_page": DEFAULT_PER_PAGE,
            "page": page,
        }
        response = _request_with_retry(
            client=client,
            method="GET",
            url=f"/repos/{repo}/commits",
            params=params,
            max_retries=max_retries,
            retry_interval=retry_interval,
            rate_limit_retries=rate_limit_retries,
            sleep_fn=sleep_fn,
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise _CollectFailed(f"意外的 commits 响应格式: {type(payload).__name__}")

        all_commits.extend(payload)
        if len(payload) < DEFAULT_PER_PAGE:
            break
        page += 1

    return all_commits


def _get_commit_detail(
    *,
    client: httpx.Client,
    repo: str,
    sha: str,
    max_retries: int,
    retry_interval: float,
    rate_limit_retries: int,
    sleep_fn: Callable[[float], None],
) -> dict[str, Any]:
    response = _request_with_retry(
        client=client,
        method="GET",
        url=f"/repos/{repo}/commits/{sha}",
        params=None,
        max_retries=max_retries,
        retry_interval=retry_interval,
        rate_limit_retries=rate_limit_retries,
        sleep_fn=sleep_fn,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise _CollectFailed(f"意外的 commit detail 响应格式: {type(payload).__name__}")
    return payload


def _request_with_retry(
    *,
    client: httpx.Client,
    method: str,
    url: str,
    params: dict[str, Any] | None,
    max_retries: int,
    retry_interval: float,
    rate_limit_retries: int,
    sleep_fn: Callable[[float], None],
) -> httpx.Response:
    attempts = 0
    rate_limit_attempts = 0

    while True:
        try:
            response = client.request(method, url, params=params)
        except httpx.TimeoutException as exc:
            attempts += 1
            if attempts >= max_retries:
                raise _CollectFailed(f"请求超时，已重试 {max_retries} 次: {url}") from exc
            logger.info(
                "GitHub API 超时，准备重试",
                extra={"url": url, "attempt": attempts, "max_retries": max_retries},
            )
            sleep_fn(retry_interval)
            continue
        except httpx.HTTPError as exc:
            attempts += 1
            if attempts >= max_retries:
                raise _CollectFailed(f"HTTP 请求失败，已重试 {max_retries} 次: {url}") from exc
            logger.info(
                "GitHub API 请求失败，准备重试",
                extra={"url": url, "attempt": attempts, "error": str(exc)},
            )
            sleep_fn(retry_interval)
            continue

        if response.status_code == 403 and _is_rate_limited(response):
            rate_limit_attempts += 1
            if rate_limit_attempts > rate_limit_retries:
                raise _CollectFailed(f"GitHub API 限流，已重试 {rate_limit_retries} 次: {url}")
            wait_seconds = _rate_limit_wait_seconds(response)
            logger.info(
                "GitHub API 限流，等待 reset 后重试",
                extra={"url": url, "wait_seconds": wait_seconds, "attempt": rate_limit_attempts},
            )
            sleep_fn(wait_seconds)
            continue

        if response.status_code >= 400:
            raise _CollectFailed(f"GitHub API 错误 HTTP {response.status_code}: {url}")

        return response


def _is_rate_limited(response: httpx.Response) -> bool:
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining == "0":
        return True
    if "Retry-After" in response.headers:
        return True
    body = response.text.lower()
    return "rate limit" in body or "api rate limit exceeded" in body


def _rate_limit_wait_seconds(response: httpx.Response) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass

    reset = response.headers.get("X-RateLimit-Reset")
    if reset is not None:
        try:
            reset_ts = int(reset)
            now_ts = int(datetime.now(timezone.utc).timestamp())
            return max(float(reset_ts - now_ts), 0.0)
        except ValueError:
            pass

    return DEFAULT_RETRY_INTERVAL


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_commit_record(
    *,
    repo: str,
    summary: dict[str, Any],
    detail: dict[str, Any],
) -> CommitRecord | None:
    commit = detail.get("commit") or summary.get("commit") or {}
    author_login = ""
    author = detail.get("author") or summary.get("author")
    if isinstance(author, dict) and author.get("login"):
        author_login = str(author["login"])
    elif isinstance(commit, dict):
        commit_author = commit.get("author") or {}
        author_login = str(commit_author.get("name") or "")

    message = ""
    if isinstance(commit, dict):
        message = str(commit.get("message") or "")

    timestamp_raw = ""
    if isinstance(commit, dict):
        commit_author = commit.get("author") or {}
        timestamp_raw = str(commit_author.get("date") or "")
    if not timestamp_raw:
        return None

    try:
        timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
    except ValueError:
        return None

    stats = detail.get("stats") or {}
    files = detail.get("files") or []
    additions = int(stats.get("additions") or 0)
    deletions = int(stats.get("deletions") or 0)
    files_changed = len(files) if isinstance(files, list) else int(stats.get("total") or 0)

    return CommitRecord(
        author=author_login,
        message=message,
        timestamp=timestamp,
        repo=repo,
        additions=additions,
        deletions=deletions,
        files_changed=files_changed,
    )
