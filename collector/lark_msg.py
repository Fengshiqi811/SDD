"""飞书消息采集模块。"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from collector.result import CollectResult
from shared.logger import get_logger

logger = get_logger("collector.lark_msg")

LARK_API_BASE = "https://open.feishu.cn"
TOKEN_URL = "/open-apis/auth/v3/tenant_access_token/internal"
MESSAGES_URL_TMPL = "/open-apis/im/v1/messages"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_INTERVAL = 5.0
PAGE_SIZE = 50

TOKEN_EXPIRED_CODES = {99991663, 99991664, 99991668}

# design.md §6.2：敏感关键词过滤
SENSITIVE_KEYWORDS = ("薪资", "绩效", "裁员")


@dataclass(frozen=True)
class MessageRecord:
    sender: str
    content: str
    timestamp: datetime
    chat_name: str


def collect(
    chat_id: str,
    keywords: list[str],
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
    sensitive_keywords: tuple[str, ...] = SENSITIVE_KEYWORDS,
) -> CollectResult[MessageRecord]:
    """采集指定群消息，按关键词过滤并屏蔽敏感词。

    token 过期时自动刷新并重试 1 次；超时时重试 max_retries 次，仍失败返回 success=False。
    """
    if not chat_id:
        return CollectResult(success=True, records=[])

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
            items = _list_messages(
                client=http_client,
                token=token,
                chat_id=chat_id,
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
                "飞书消息采集失败",
                extra={"chat_id": chat_id, "error": str(exc)},
            )
            return CollectResult(success=False, records=[], error_message=str(exc))

        records: list[MessageRecord] = []
        for item in items:
            record = _to_message_record(item, since=since, until=until)
            if record is None:
                continue
            if not _matches_keywords(record.content, keywords):
                continue
            if _contains_sensitive(record.content, sensitive_keywords):
                continue
            records.append(record)
        return CollectResult(success=True, records=records)
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


def _list_messages(
    *,
    client: httpx.Client,
    token: str,
    chat_id: str,
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
            "container_id_type": "chat",
            "container_id": chat_id,
            "page_size": PAGE_SIZE,
            "start_time": str(_to_seconds(since)),
            "end_time": str(_to_seconds(until)),
        }
        if page_token:
            params["page_token"] = page_token

        try:
            response = _request_api(
                client=client,
                method="GET",
                url=MESSAGES_URL_TMPL,
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
                    url=MESSAGES_URL_TMPL,
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
            raise _CollectFailed("消息列表响应格式错误")

        data = payload.get("data") or {}
        page_items = data.get("items") or []
        if not isinstance(page_items, list):
            raise _CollectFailed("消息列表 items 格式错误")
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
                "飞书消息 API 超时，准备重试",
                extra={"url": url, "attempt": attempts, "max_retries": max_retries},
            )
            sleep_fn(retry_interval)


def _to_message_record(
    item: dict[str, Any],
    *,
    since: datetime,
    until: datetime,
) -> MessageRecord | None:
    content = _extract_content(item)
    if not content:
        return None

    timestamp = _parse_datetime(
        item.get("timestamp") or item.get("create_time") or item.get("created_at")
    )
    if timestamp is None:
        return None

    ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    since_cmp = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
    until_cmp = until if until.tzinfo else until.replace(tzinfo=timezone.utc)
    if ts < since_cmp or ts > until_cmp:
        return None

    sender = _extract_sender(item)
    chat_name = str(item.get("chat_name") or item.get("chat_id") or "")

    return MessageRecord(
        sender=sender,
        content=content,
        timestamp=timestamp,
        chat_name=chat_name,
    )


def _extract_content(item: dict[str, Any]) -> str:
    for key in ("content", "text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value

    body = item.get("body")
    if isinstance(body, dict):
        raw = body.get("content")
        if isinstance(raw, str) and raw.strip():
            # 飞书消息 body.content 可能是 JSON 字符串：{"text":"..."}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("text"):
                    return str(parsed["text"])
            except json.JSONDecodeError:
                pass
            return raw
    return ""


def _extract_sender(item: dict[str, Any]) -> str:
    if item.get("sender"):
        sender = item["sender"]
        if isinstance(sender, str):
            return sender
        if isinstance(sender, dict):
            return str(
                sender.get("id")
                or sender.get("sender_id")
                or sender.get("user_id")
                or sender.get("open_id")
                or ""
            )

    sender_id = item.get("sender_id")
    if isinstance(sender_id, dict):
        return str(sender_id.get("user_id") or sender_id.get("open_id") or "")
    if sender_id:
        return str(sender_id)
    return ""


def _matches_keywords(content: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    return any(keyword and keyword in content for keyword in keywords)


def _contains_sensitive(content: str, sensitive_keywords: tuple[str, ...]) -> bool:
    return any(word in content for word in sensitive_keywords)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "" or value == 0:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        if value.isdigit():
            return _parse_datetime(int(value))
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _to_seconds(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())
