"""GitHub 科研代码活动采集：提交之外的 PR、Issue、代码评审。"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

from shared.logger import get_logger

logger = get_logger("collector.github_activity")

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0


def collect_activity(
    repos: list[str],
    since: datetime,
    until: datetime,
    username: str,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """统计指定用户在仓库中的 PR、Issue 和代码评审活动。"""
    result: dict[str, Any] = {
        "success": True,
        "error": None,
        "pull_requests": [],
        "issues": [],
        "reviews": [],
        "counts": {"pull_requests": 0, "issues": 0, "reviews": 0},
    }
    if not repos or not username:
        return result

    auth_token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "daily-report-activity",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    owns_client = client is None
    http_client = client or httpx.Client(base_url=GITHUB_API_BASE, headers=headers, timeout=timeout)
    errors: list[str] = []
    date_range = f"{since.date().isoformat()}..{until.date().isoformat()}"

    try:
        for repo in repos:
            try:
                prs = _search(http_client, f"repo:{repo} type:pr author:{username} updated:{date_range}")
                issues = _search(http_client, f"repo:{repo} type:issue author:{username} updated:{date_range}")
                reviews = _search(
                    http_client,
                    f"repo:{repo} type:pr reviewed-by:{username} updated:{date_range}",
                )
                result["pull_requests"].extend(_normalize(repo, prs, "pull_request"))
                result["issues"].extend(_normalize(repo, issues, "issue"))
                result["reviews"].extend(_normalize(repo, reviews, "review"))
            except Exception as exc:  # noqa: BLE001
                logger.error("GitHub 活动采集失败", extra={"repo": repo, "error": str(exc)})
                errors.append(f"{repo}: {exc}")
    finally:
        if owns_client:
            http_client.close()

    result["counts"] = {
        "pull_requests": len(result["pull_requests"]),
        "issues": len(result["issues"]),
        "reviews": len(result["reviews"]),
    }
    if errors and not any(result["counts"].values()):
        result["success"] = False
        result["error"] = "; ".join(errors)
    elif errors:
        result["error"] = "; ".join(errors)
    return result


def _search(client: httpx.Client, query: str) -> list[dict[str, Any]]:
    response = client.get("/search/issues", params={"q": query, "per_page": 100})
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {query}")
    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else None
    return items if isinstance(items, list) else []


def _normalize(repo: str, items: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    records = []
    for item in items:
        number = item.get("number")
        records.append(
            {
                "repo": repo,
                "number": number,
                "title": str(item.get("title") or ""),
                "state": str(item.get("state") or ""),
                "kind": kind,
                "url": str(item.get("html_url") or ""),
                "created_at": str(item.get("created_at") or ""),
                "updated_at": str(item.get("updated_at") or ""),
                "branch": "",
            }
        )
    return records