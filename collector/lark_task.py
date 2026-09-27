"""飞书任务采集模块。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from shared.logger import get_logger

logger = get_logger("collector.lark_task")

LARK_API_BASE = "https://open.feishu.cn"
TOKEN_URL = "/open-apis/auth/v3/tenant_access_token/internal"
# project_id 对应飞书任务清单（tasklist）guid
TASKS_URL_TMPL = "/open-apis/task/v2/tasklists/{project_id}/tasks"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_INTERVAL = 5.0
PAGE_SIZE = 50

# 飞书常见 token 失效错误码
TOKEN_EXPIRED_CODES = {99991663, 99991664, 99991668}


@dataclass(frozen=True)
class TaskRecord:
    assignee: str
    title: str
    status_from: str
    status_to: str
    updated_at: datetime


def collect(
    project_id: str,
    since: datetime,
    until: datetime,
    *,
    app_id: str | None = None,
    app_secret: str | None = None,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_interval: float = DEFAULT_RETRY_INTERVAL,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[TaskRecord]:
    """采集指定项目在时间窗口内发生状态变更的任务。

    token 过期时自动刷新并重试 1 次；超时时重试 max_retries 次，仍失败返回空列表。
    """
    if not project_id:
        return []

    resolved_app_id = app_id if app_id is not None else os.getenv("LARK_APP_ID", "")
    resolved_app_secret = app_secret if app_secret is not None else os.getenv("LARK_APP_SECRET", "")

    owns_client = client is None
    http_client = client or httpx.Client(base_url=LARK_API_BASE, timeout=timeout)

    try:
        try:
            token = _fetch_tenant_access_token(
                client=http_client,
                app_id=resolved_app_id,
                app_secret=resolved_app_secret,
                max_retries=max_retries,
                retry_interval=retry_interval,
                sleep_fn=sleep_fn,
            )
            items = _list_changed_tasks(
                client=http_client,
                token=token,
                project_id=project_id,
                since=since,
                until=until,
                app_id=resolved_app_id,
                app_secret=resolved_app_secret,
                max_retries=max_retries,
                retry_interval=retry_interval,
                sleep_fn=sleep_fn,
            )
        except _CollectFailed as exc:
            logger.error(
                "飞书任务采集失败，返回空列表",
                extra={"project_id": project_id, "error": str(exc)},
            )
            return []

        records: list[TaskRecord] = []
        for item in items:
            record = _to_task_record(item, since=since, until=until)
            if record is not None:
                records.append(record)
        return records
    finally:
        if owns_client:
            http_client.close()


class _CollectFailed(Exception):
    """内部：重试耗尽后的采集失败。"""


class _TokenExpired(Exception):
    """内部：access token 已过期。"""


def _fetch_tenant_access_token(
    *,
    client: httpx.Client,
    app_id: str,
    app_secret: str,
    max_retries: int,
    retry_interval: float,
    sleep_fn: Callable[[float], None],
) -> str:
    response = _request_with_timeout_retry(
        client=client,
        method="POST",
        url=TOKEN_URL,
        headers={"Content-Type": "application/json; charset=utf-8"},
        json_body={"app_id": app_id, "app_secret": app_secret},
        max_retries=max_retries,
        retry_interval=retry_interval,
        sleep_fn=sleep_fn,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise _CollectFailed("获取 tenant_access_token 响应格式错误")
    if payload.get("code", 0) != 0:
        raise _CollectFailed(f"获取 tenant_access_token 失败: {payload.get('msg')}")
    token = payload.get("tenant_access_token")
    if not token:
        raise _CollectFailed("获取 tenant_access_token 失败: 响应缺少 token")
    return str(token)


def _list_changed_tasks(
    *,
    client: httpx.Client,
    token: str,
    project_id: str,
    since: datetime,
    until: datetime,
    app_id: str,
    app_secret: str,
    max_retries: int,
    retry_interval: float,
    sleep_fn: Callable[[float], None],
) -> list[dict[str, Any]]:
    page_token: str | None = None
    items: list[dict[str, Any]] = []
    current_token = token
    token_refreshed = False

    while True:
        params: dict[str, Any] = {
            "page_size": PAGE_SIZE,
            "completed": "false",
            "updated_from": _to_ms(since),
            "updated_to": _to_ms(until),
        }
        if page_token:
            params["page_token"] = page_token

        try:
            response = _request_api(
                client=client,
                method="GET",
                url=TASKS_URL_TMPL.format(project_id=project_id),
                token=current_token,
                params=params,
                max_retries=max_retries,
                retry_interval=retry_interval,
                sleep_fn=sleep_fn,
            )
        except _TokenExpired:
            if token_refreshed:
                raise _CollectFailed("飞书 token 刷新后仍失效")
            logger.info("飞书 token 过期，自动刷新后重试 1 次")
            current_token = _fetch_tenant_access_token(
                client=client,
                app_id=app_id,
                app_secret=app_secret,
                max_retries=max_retries,
                retry_interval=retry_interval,
                sleep_fn=sleep_fn,
            )
            token_refreshed = True
            try:
                response = _request_api(
                    client=client,
                    method="GET",
                    url=TASKS_URL_TMPL.format(project_id=project_id),
                    token=current_token,
                    params=params,
                    max_retries=max_retries,
                    retry_interval=retry_interval,
                    sleep_fn=sleep_fn,
                )
            except _TokenExpired as exc:
                raise _CollectFailed("飞书 token 刷新后仍失效") from exc

        payload = response.json()
        if not isinstance(payload, dict):
            raise _CollectFailed("任务列表响应格式错误")

        data = payload.get("data") or {}
        page_items = data.get("items") or data.get("tasks") or []
        if not isinstance(page_items, list):
            raise _CollectFailed("任务列表 items 格式错误")
        items.extend(page_items)

        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break

    return items


def _request_api(
    *,
    client: httpx.Client,
    method: str,
    url: str,
    token: str,
    params: dict[str, Any] | None,
    max_retries: int,
    retry_interval: float,
    sleep_fn: Callable[[float], None],
) -> httpx.Response:
    response = _request_with_timeout_retry(
        client=client,
        method=method,
        url=url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        params=params,
        max_retries=max_retries,
        retry_interval=retry_interval,
        sleep_fn=sleep_fn,
    )

    if response.status_code == 401:
        raise _TokenExpired("HTTP 401")

    payload = response.json()
    if isinstance(payload, dict):
        code = payload.get("code", 0)
        if code in TOKEN_EXPIRED_CODES:
            raise _TokenExpired(f"code={code}")
        if code != 0:
            raise _CollectFailed(f"飞书 API 错误 code={code}: {payload.get('msg')}")

    if response.status_code >= 400:
        raise _CollectFailed(f"飞书 API HTTP {response.status_code}: {url}")

    return response


def _request_with_timeout_retry(
    *,
    client: httpx.Client,
    method: str,
    url: str,
    headers: dict[str, str],
    max_retries: int,
    retry_interval: float,
    sleep_fn: Callable[[float], None],
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    attempts = 0
    while True:
        try:
            return client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
            )
        except httpx.TimeoutException as exc:
            attempts += 1
            if attempts >= max_retries:
                raise _CollectFailed(f"请求超时，已重试 {max_retries} 次: {url}") from exc
            logger.info(
                "飞书任务 API 超时，准备重试",
                extra={"url": url, "attempt": attempts, "max_retries": max_retries},
            )
            sleep_fn(retry_interval)


def _to_task_record(
    item: dict[str, Any],
    *,
    since: datetime,
    until: datetime,
) -> TaskRecord | None:
    title = str(item.get("summary") or item.get("title") or "")
    if not title:
        return None

    status_to = str(item.get("status") or item.get("status_to") or "")
    status_from = str(item.get("status_from") or item.get("previous_status") or "")
    if not status_to:
        return None
    if not status_from:
        # 无显式原状态时，按完成态做保守推断
        status_from = "todo" if status_to == "done" else "unknown"

    updated_raw = item.get("updated_at") or item.get("update_time") or item.get("completed_at")
    updated_at = _parse_datetime(updated_raw)
    if updated_at is None:
        return None

    # 仅保留窗口内变更
    updated_cmp = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    since_cmp = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
    until_cmp = until if until.tzinfo else until.replace(tzinfo=timezone.utc)
    if updated_cmp < since_cmp or updated_cmp > until_cmp:
        return None

    assignee = _extract_assignee(item)
    return TaskRecord(
        assignee=assignee,
        title=title,
        status_from=status_from,
        status_to=status_to,
        updated_at=updated_at,
    )


def _extract_assignee(item: dict[str, Any]) -> str:
    if item.get("assignee"):
        return str(item["assignee"])

    members = item.get("members") or item.get("assignees") or []
    if isinstance(members, list):
        for member in members:
            if not isinstance(member, dict):
                continue
            role = str(member.get("role") or "").lower()
            if role in {"assignee", "owner", ""}:
                return str(
                    member.get("id")
                    or member.get("username")
                    or member.get("name")
                    or member.get("member_id")
                    or ""
                )
    return ""


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "" or value == 0:
        return None
    if isinstance(value, (int, float)):
        # 飞书常见秒/毫秒时间戳
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)
