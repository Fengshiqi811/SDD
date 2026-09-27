"""邮件推送：通过 SMTP 发送 HTML 日报。"""

from __future__ import annotations

import os
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Callable

from generator.formatter import DailyReport
from shared.logger import get_logger

logger = get_logger("notifier.email")

DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_INTERVAL = 5.0


def send(
    report: DailyReport,
    recipients: list[str],
    *,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_interval: float = DEFAULT_RETRY_INTERVAL,
    sleep_fn: Callable[[float], None] = time.sleep,
    smtp_factory: Callable[[str, int], Any] | None = None,
) -> bool:
    """将 HTML 日报通过 SMTP 发送给收件人。

    发送失败时重试 max_retries 次；仍失败返回 False 并记录错误日志。
    """
    if not recipients:
        logger.error("邮件推送失败：收件人为空")
        return False

    host = smtp_host if smtp_host is not None else os.getenv("SMTP_HOST", "")
    port = smtp_port if smtp_port is not None else int(os.getenv("SMTP_PORT", "587"))
    user = smtp_user if smtp_user is not None else os.getenv("SMTP_USER", "")
    password = smtp_password if smtp_password is not None else os.getenv("SMTP_PASSWORD", "")
    factory = smtp_factory or (lambda h, p: smtplib.SMTP(h, p, timeout=30))

    message = _build_message(report=report, recipients=recipients, sender=user or "noreply@localhost")
    attempts = max_retries + 1  # 首次 + 重试次数
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            _deliver(
                factory=factory,
                host=host,
                port=port,
                user=user,
                password=password,
                message=message,
            )
            logger.info(
                "邮件推送成功",
                extra={"recipients": recipients, "subject": message["Subject"]},
            )
            return True
        except Exception as exc:  # noqa: BLE001 — 推送层统一捕获后重试/降级
            last_error = exc
            if attempt >= attempts:
                break
            logger.info(
                "邮件推送失败，准备重试",
                extra={"attempt": attempt, "max_retries": max_retries, "error": str(exc)},
            )
            sleep_fn(retry_interval)

    logger.error(
        "邮件推送失败",
        extra={
            "recipients": recipients,
            "retries": max_retries,
            "error": str(last_error) if last_error else "unknown",
        },
    )
    return False


def _build_message(
    *,
    report: DailyReport,
    recipients: list[str],
    sender: str,
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"{report.team_name} 日报 {report.date.isoformat()}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(report.html, subtype="html")
    return msg


def _deliver(
    *,
    factory: Callable[[str, int], Any],
    host: str,
    port: int,
    user: str,
    password: str,
    message: EmailMessage,
) -> None:
    client = factory(host, port)
    try:
        if hasattr(client, "ehlo"):
            try:
                client.ehlo()
            except Exception:  # noqa: BLE001
                pass
        if hasattr(client, "starttls"):
            try:
                client.starttls()
                if hasattr(client, "ehlo"):
                    client.ehlo()
            except Exception:  # noqa: BLE001 — mock / 无 TLS 环境可忽略
                pass
        if user and hasattr(client, "login"):
            client.login(user, password)
        client.send_message(message)
    finally:
        if hasattr(client, "quit"):
            try:
                client.quit()
            except Exception:  # noqa: BLE001
                pass
        elif hasattr(client, "close"):
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
