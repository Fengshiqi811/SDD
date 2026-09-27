"""notifier/email.py 单元测试（mock SMTP）— TDD 先红后绿。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from email.message import Message
from unittest.mock import MagicMock

from generator.formatter import DailyReport, MemberReport
from notifier.email import send

REPORT_DATE = date(2026, 9, 27)
TEAM = "研发团队"
RECIPIENTS = ["leader@company.com", "pm@company.com"]


def _sample_report() -> DailyReport:
    return DailyReport(
        date=REPORT_DATE,
        team_name=TEAM,
        members=[
            MemberReport(
                name="张三",
                github_username="zhangsan",
                commits=[],
                tasks=[],
                messages=[],
            )
        ],
        generated_at=datetime(2026, 9, 27, 18, 0, 0, tzinfo=timezone.utc),
        markdown="# 研发团队 日报 2026-09-27\n",
        html="<!DOCTYPE html><html><body><h1>研发团队 日报 2026-09-27</h1></body></html>",
    )


def test_send_signature_returns_bool_on_success():
    report = _sample_report()
    smtp = MagicMock()

    result = send(
        report,
        RECIPIENTS,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="bot@company.com",
        smtp_password="secret",
        smtp_factory=lambda host, port: smtp,
    )

    assert result is True
    assert smtp.send_message.called


def test_subject_contains_date_and_team_name():
    report = _sample_report()
    smtp = MagicMock()
    captured: dict[str, Message] = {}

    def capture_send_message(msg: Message, **kwargs):
        captured["msg"] = msg

    smtp.send_message.side_effect = capture_send_message

    assert send(
        report,
        RECIPIENTS,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="bot@company.com",
        smtp_password="secret",
        smtp_factory=lambda host, port: smtp,
    )

    msg = captured["msg"]
    subject = msg["Subject"]
    assert "2026-09-27" in subject
    assert "研发团队" in subject


def test_body_is_html_daily_report():
    report = _sample_report()
    smtp = MagicMock()
    captured: dict[str, Message] = {}

    def capture_send_message(msg: Message, **kwargs):
        captured["msg"] = msg

    smtp.send_message.side_effect = capture_send_message

    send(
        report,
        RECIPIENTS,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="bot@company.com",
        smtp_password="secret",
        smtp_factory=lambda host, port: smtp,
    )

    msg = captured["msg"]
    assert msg.get_content_type() == "text/html" or "html" in (msg.get_content_type() or "")
    payload = msg.get_content() if hasattr(msg, "get_content") else msg.get_payload()
    body = payload if isinstance(payload, str) else str(payload)
    assert "<html" in body.lower() or "<h1" in body.lower()
    assert "研发团队 日报 2026-09-27" in body


def test_send_failure_retries_twice_then_returns_false(caplog):
    report = _sample_report()
    smtp = MagicMock()
    smtp.send_message.side_effect = OSError("SMTP connection failed")
    sleeps: list[float] = []

    with caplog.at_level("ERROR"):
        result = send(
            report,
            RECIPIENTS,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="bot@company.com",
            smtp_password="secret",
            smtp_factory=lambda host, port: smtp,
            max_retries=2,
            retry_interval=1.0,
            sleep_fn=sleeps.append,
        )

    assert result is False
    # 首次 + 重试 2 次 = 3 次
    assert smtp.send_message.call_count == 3
    assert sleeps == [1.0, 1.0]
    assert any("邮件推送失败" in message for message in caplog.messages)


def test_recipients_passed_to_smtp():
    report = _sample_report()
    smtp = MagicMock()
    captured: dict[str, Message] = {}

    def capture_send_message(msg: Message, **kwargs):
        captured["msg"] = msg

    smtp.send_message.side_effect = capture_send_message

    send(
        report,
        RECIPIENTS,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="bot@company.com",
        smtp_password="secret",
        smtp_factory=lambda host, port: smtp,
    )

    msg = captured["msg"]
    to_header = msg["To"]
    assert "leader@company.com" in to_header
    assert "pm@company.com" in to_header
