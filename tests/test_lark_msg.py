"""collector/lark_msg.py 单元测试（mock 飞书消息 API）— TDD 先红后绿。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import httpx

from collector.lark_msg import MessageRecord, collect

SINCE = datetime(2026, 9, 27, 0, 0, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 9, 27, 18, 0, 0, tzinfo=timezone.utc)
CHAT_ID = "oc_chat_001"
KEYWORDS = ["进度", "阻塞", "评审"]


def _mock_response(
    status_code: int = 200,
    json_data: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://open.feishu.cn/test")
    return httpx.Response(
        status_code=status_code,
        json=json_data if json_data is not None else {},
        headers=headers or {},
        request=request,
    )


def _token_ok(token: str = "t-valid") -> httpx.Response:
    return _mock_response(
        json_data={"code": 0, "msg": "ok", "tenant_access_token": token, "expire": 7200}
    )


def _msg_item(
    *,
    sender: str = "zhangsan@company.com",
    content: str = "今日进度正常",
    timestamp: str = "2026-09-27T10:00:00+00:00",
    chat_name: str = "研发群",
) -> dict[str, Any]:
    return {
        "sender": sender,
        "content": content,
        "text": content,
        "create_time": timestamp,
        "timestamp": timestamp,
        "chat_name": chat_name,
        "body": {"content": content},
    }


def _messages_ok(items: list[dict[str, Any]]) -> httpx.Response:
    return _mock_response(
        json_data={
            "code": 0,
            "data": {
                "items": items,
                "has_more": False,
            },
        }
    )


def test_collect_signature_and_message_record_fields():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok(),
        _messages_ok([_msg_item(content="项目进度同步：登录页已完成")]),
    ]

    result = collect(
        CHAT_ID,
        KEYWORDS,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )

    records = result.records
    assert result.success is True
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, MessageRecord)
    assert record.sender == "zhangsan@company.com"
    assert "进度" in record.content
    assert isinstance(record.timestamp, datetime)
    assert record.chat_name == "研发群"


def test_keyword_filter_keeps_only_matching_messages():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok(),
        _messages_ok(
            [
                _msg_item(content="今天天气不错"),
                _msg_item(content="登录接口有阻塞，需要支援"),
                _msg_item(content="下午三点评审方案"),
                _msg_item(content="一起吃饭吗"),
            ]
        ),
    ]

    result = collect(
        CHAT_ID,
        KEYWORDS,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )
    records = result.records

    contents = [r.content for r in records]
    assert contents == [
        "登录接口有阻塞，需要支援",
        "下午三点评审方案",
    ]


def test_sensitive_keywords_are_filtered_out():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok(),
        _messages_ok(
            [
                _msg_item(content="本周进度汇报已发送"),
                _msg_item(content="讨论薪资调整的进度安排"),
                _msg_item(content="绩效结果相关评审推迟"),
                _msg_item(content="关于裁员的阻塞风险"),
                _msg_item(content="阻塞问题已解决，进度恢复"),
            ]
        ),
    ]

    result = collect(
        CHAT_ID,
        KEYWORDS,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )
    records = result.records

    contents = [r.content for r in records]
    assert "讨论薪资调整的进度安排" not in contents
    assert "绩效结果相关评审推迟" not in contents
    assert "关于裁员的阻塞风险" not in contents
    assert contents == [
        "本周进度汇报已发送",
        "阻塞问题已解决，进度恢复",
    ]


def test_token_expired_auto_refresh_and_retry_once():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok("t-old"),
        _mock_response(json_data={"code": 99991663, "msg": "token expired"}),
        _token_ok("t-new"),
        _messages_ok([_msg_item(content="刷新后拿到进度更新")]),
    ]

    result = collect(
        CHAT_ID,
        KEYWORDS,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )

    records = result.records
    assert result.success is True
    assert len(records) == 1
    assert records[0].content == "刷新后拿到进度更新"
    assert client.request.call_count == 4
    retry_call = client.request.call_args_list[3]
    assert retry_call.kwargs["headers"]["Authorization"] == "Bearer t-new"


def test_timeout_retries_three_times_then_returns_empty(caplog):
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = httpx.TimeoutException("timed out")
    sleeps: list[float] = []

    with caplog.at_level("ERROR"):
        result = collect(
            CHAT_ID,
            KEYWORDS,
            SINCE,
            UNTIL,
            app_id="app-id",
            app_secret="app-secret",
            client=client,
            max_retries=3,
            retry_interval=5.0,
            sleep_fn=sleeps.append,
        )

    assert result.success is False
    assert result.records == []
    assert client.request.call_count == 3
    assert sleeps == [5.0, 5.0]
    assert any("飞书消息采集失败" in message for message in caplog.messages)
