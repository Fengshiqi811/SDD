"""notifier/lark_bot.py 单元测试（mock webhook）— TDD 先红后绿。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import httpx

from generator.formatter import DailyReport, MemberReport
from notifier.lark_bot import send

REPORT_DATE = date(2026, 9, 27)
TEAM = "研发团队"
CHAT_ID = "oc_notify_chat_001"
MARKDOWN = "# 研发团队 日报 2026-09-27\n\n## 张三\n\n### 代码提交\n- fix: login\n"


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
        markdown=MARKDOWN,
        html="<html><body><h1>日报</h1></body></html>",
    )


def _mock_response(status_code: int = 200, json_data: Any = None) -> httpx.Response:
    request = httpx.Request("POST", "https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
    return httpx.Response(
        status_code=status_code,
        json=json_data if json_data is not None else {"code": 0, "msg": "success"},
        request=request,
    )


def test_send_signature_returns_bool_on_success():
    report = _sample_report()
    client = MagicMock(spec=httpx.Client)
    client.request.return_value = _mock_response()

    result = send(
        report,
        CHAT_ID,
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        client=client,
        sleep_fn=lambda _: None,
    )

    assert result is True
    assert client.request.called


def test_send_payload_is_markdown_daily_report():
    report = _sample_report()
    client = MagicMock(spec=httpx.Client)
    client.request.return_value = _mock_response()

    send(
        report,
        CHAT_ID,
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        client=client,
        sleep_fn=lambda _: None,
    )

    call = client.request.call_args
    assert call.args[0] == "POST"
    payload = call.kwargs.get("json") or {}
    assert payload.get("msg_type") == "text" or "markdown" in str(payload).lower() or payload.get("msg_type") == "interactive"

    # 正文应包含 Task6 生成的 Markdown 日报内容
    serialized = str(payload)
    assert "研发团队 日报 2026-09-27" in serialized
    assert "代码提交" in serialized
    assert report.markdown.strip() in serialized or "fix: login" in serialized


def test_send_failure_retries_twice_then_returns_false(caplog):
    report = _sample_report()
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = httpx.TimeoutException("webhook timeout")
    sleeps: list[float] = []

    with caplog.at_level("ERROR"):
        result = send(
            report,
            CHAT_ID,
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
            client=client,
            max_retries=2,
            retry_interval=1.0,
            sleep_fn=sleeps.append,
        )

    assert result is False
    assert client.request.call_count == 3  # 首次 + 重试 2 次
    assert sleeps == [1.0, 1.0]
    assert any("飞书推送失败" in message for message in caplog.messages)


def test_http_error_response_retries_then_fails(caplog):
    report = _sample_report()
    client = MagicMock(spec=httpx.Client)
    client.request.return_value = _mock_response(
        status_code=500,
        json_data={"code": 500, "msg": "internal error"},
    )
    sleeps: list[float] = []

    with caplog.at_level("ERROR"):
        result = send(
            report,
            CHAT_ID,
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
            client=client,
            max_retries=2,
            retry_interval=0.5,
            sleep_fn=sleeps.append,
        )

    assert result is False
    assert client.request.call_count == 3
    assert any("飞书推送失败" in message for message in caplog.messages)
