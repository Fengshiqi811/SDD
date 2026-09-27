"""飞书机器人推送：通过 webhook 发送 Markdown 日报。"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

from generator.formatter import DailyReport
from shared.logger import get_logger

logger = get_logger("notifier.lark_bot")

DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_INTERVAL = 5.0
DEFAULT_TIMEOUT = 30.0


def send(
    report: DailyReport,
    chat_id: str,
    *,
    webhook_url: str | None = None,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_interval: float = DEFAULT_RETRY_INTERVAL,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    """将 Markdown 日报通过飞书机器人 webhook 发送到指定群。

    发送失败时重试 max_retries 次；仍失败返回 False 并记录错误日志。
    chat_id 用于日志关联；实际投递地址由 webhook_url / 环境变量决定。
    """
    url = webhook_url if webhook_url is not None else os.getenv("LARK_BOT_WEBHOOK", "")
    if not url:
        logger.error("飞书推送失败：未配置 webhook", extra={"chat_id": chat_id})
        return False

    payload = _build_markdown_payload(report)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    attempts = max_retries + 1
    last_error: str | None = None

    try:
        for attempt in range(1, attempts + 1):
            try:
                response = http_client.request("POST", url, json=payload)
                if response.status_code >= 400:
                    raise _SendFailed(f"HTTP {response.status_code}")

                body = response.json() if response.content else {}
                if isinstance(body, dict):
                    code = body.get("code", body.get("StatusCode", 0))
                    if code not in (0, None, "0"):
                        raise _SendFailed(f"webhook code={code}: {body.get('msg') or body.get('StatusMessage')}")

                logger.info(
                    "飞书推送成功",
                    extra={"chat_id": chat_id, "date": report.date.isoformat()},
                )
                return True
            except (httpx.HTTPError, _SendFailed, ValueError) as exc:
                last_error = str(exc)
                if attempt >= attempts:
                    break
                logger.info(
                    "飞书推送失败，准备重试",
                    extra={"chat_id": chat_id, "attempt": attempt, "error": last_error},
                )
                sleep_fn(retry_interval)

        logger.error(
            "飞书推送失败",
            extra={"chat_id": chat_id, "retries": max_retries, "error": last_error or "unknown"},
        )
        return False
    finally:
        if owns_client:
            http_client.close()


class _SendFailed(Exception):
    """内部：单次 webhook 发送失败。"""


def _build_markdown_payload(report: DailyReport) -> dict[str, Any]:
    """构造飞书自定义机器人 Markdown 消息体。"""
    title = f"{report.team_name} 日报 {report.date.isoformat()}"
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": report.markdown,
                }
            ],
        },
    }
