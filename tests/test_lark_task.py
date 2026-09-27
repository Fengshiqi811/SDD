"""collector/lark_task.py 单元测试（mock 飞书 API）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import httpx

from collector.lark_task import TaskRecord, collect

SINCE = datetime(2026, 9, 27, 0, 0, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 9, 27, 18, 0, 0, tzinfo=timezone.utc)
PROJECT_ID = "tasklist-guid-001"


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


def _task_item(
    *,
    title: str = "完成登录页",
    assignee: str = "zhangsan@company.com",
    status_from: str = "todo",
    status_to: str = "done",
    updated_at: str = "2026-09-27T10:30:00+00:00",
) -> dict[str, Any]:
    return {
        "summary": title,
        "assignee": assignee,
        "status_from": status_from,
        "status": status_to,
        "updated_at": updated_at,
        "members": [{"id": assignee, "role": "assignee"}],
    }


def test_collect_signature_and_task_record_fields():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok(),
        _mock_response(
            json_data={
                "code": 0,
                "data": {
                    "items": [_task_item()],
                    "has_more": False,
                },
            }
        ),
    ]

    records = collect(
        PROJECT_ID,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, TaskRecord)
    assert record.assignee == "zhangsan@company.com"
    assert record.title == "完成登录页"
    assert record.status_from == "todo"
    assert record.status_to == "done"
    assert isinstance(record.updated_at, datetime)


def test_token_expired_auto_refresh_and_retry_once():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok("t-old"),
        # 业务请求：token 过期
        _mock_response(json_data={"code": 99991663, "msg": "token expired"}),
        # 刷新 token
        _token_ok("t-new"),
        # 重试成功
        _mock_response(
            json_data={
                "code": 0,
                "data": {
                    "items": [
                        _task_item(
                            title="修复缺陷",
                            assignee="lisi@company.com",
                            status_from="in_progress",
                            status_to="done",
                        )
                    ],
                    "has_more": False,
                },
            }
        ),
    ]

    records = collect(
        PROJECT_ID,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )

    assert len(records) == 1
    assert records[0].title == "修复缺陷"
    assert records[0].assignee == "lisi@company.com"
    assert client.request.call_count == 4

    # 重试业务请求时使用新 token
    retry_call = client.request.call_args_list[3]
    assert retry_call.kwargs["headers"]["Authorization"] == "Bearer t-new"


def test_timeout_retries_three_times_then_returns_empty(caplog):
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = httpx.TimeoutException("timed out")
    sleeps: list[float] = []

    with caplog.at_level("ERROR"):
        records = collect(
            PROJECT_ID,
            SINCE,
            UNTIL,
            app_id="app-id",
            app_secret="app-secret",
            client=client,
            max_retries=3,
            retry_interval=5.0,
            sleep_fn=sleeps.append,
        )

    assert records == []
    assert client.request.call_count == 3
    assert sleeps == [5.0, 5.0]
    assert any("飞书任务采集失败" in message for message in caplog.messages)


def test_filters_tasks_outside_time_window():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok(),
        _mock_response(
            json_data={
                "code": 0,
                "data": {
                    "items": [
                        _task_item(title="当天任务", updated_at="2026-09-27T12:00:00+00:00"),
                        _task_item(title="过期任务", updated_at="2026-09-26T12:00:00+00:00"),
                    ],
                    "has_more": False,
                },
            }
        ),
    ]

    records = collect(
        PROJECT_ID,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )

    assert [r.title for r in records] == ["当天任务"]


def test_http_401_triggers_token_refresh():
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = [
        _token_ok("t-1"),
        _mock_response(status_code=401, json_data={"code": 401, "msg": "unauthorized"}),
        _token_ok("t-2"),
        _mock_response(
            json_data={
                "code": 0,
                "data": {"items": [_task_item(title="401恢复")], "has_more": False},
            }
        ),
    ]

    records = collect(
        PROJECT_ID,
        SINCE,
        UNTIL,
        app_id="app-id",
        app_secret="app-secret",
        client=client,
        sleep_fn=lambda _: None,
    )

    assert len(records) == 1
    assert records[0].title == "401恢复"
