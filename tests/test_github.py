"""collector/github.py 单元测试（mock GitHub API）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from collector.github import CommitRecord, collect

SINCE = datetime(2026, 9, 27, 0, 0, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 9, 27, 18, 0, 0, tzinfo=timezone.utc)


def _commit_summary(sha: str, login: str, message: str, date: str) -> dict[str, Any]:
    return {
        "sha": sha,
        "author": {"login": login},
        "commit": {
            "message": message,
            "author": {"name": login, "date": date},
        },
    }


def _commit_detail(
    sha: str,
    login: str,
    message: str,
    date: str,
    additions: int,
    deletions: int,
    files: list[str],
) -> dict[str, Any]:
    return {
        "sha": sha,
        "author": {"login": login},
        "commit": {
            "message": message,
            "author": {"name": login, "date": date},
        },
        "stats": {"additions": additions, "deletions": deletions, "total": additions + deletions},
        "files": [{"filename": name} for name in files],
    }


def _mock_response(
    status_code: int = 200,
    json_data: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://api.github.com/test")
    return httpx.Response(
        status_code=status_code,
        json=json_data if json_data is not None else {},
        headers=headers or {},
        request=request,
    )


def test_collect_signature_and_commit_record_fields():
    client = MagicMock(spec=httpx.Client)
    summary = _commit_summary(
        "abc123",
        "zhangsan",
        "fix: login bug",
        "2026-09-27T10:00:00Z",
    )
    detail = _commit_detail(
        "abc123",
        "zhangsan",
        "fix: login bug",
        "2026-09-27T10:00:00Z",
        additions=12,
        deletions=3,
        files=["a.py", "b.py"],
    )
    client.request.side_effect = [
        _mock_response(json_data=[summary]),
        _mock_response(json_data=detail),
    ]

    result = collect(["org/repo-a"], SINCE, UNTIL, client=client, sleep_fn=lambda _: None)

    records = result.records
    assert result.success is True
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, CommitRecord)
    assert record.author == "zhangsan"
    assert record.message == "fix: login bug"
    assert isinstance(record.timestamp, datetime)
    assert record.repo == "org/repo-a"
    assert record.additions == 12
    assert record.deletions == 3
    assert record.files_changed == 2


def test_collect_supports_pagination():
    client = MagicMock(spec=httpx.Client)
    page1 = [
        _commit_summary(f"sha-{i}", "dev", f"msg-{i}", "2026-09-27T10:00:00Z")
        for i in range(30)
    ]
    page2 = [
        _commit_summary("sha-30", "dev", "msg-30", "2026-09-27T11:00:00Z"),
    ]

    responses: list[httpx.Response] = [_mock_response(json_data=page1), _mock_response(json_data=page2)]
    for item in page1 + page2:
        responses.append(
            _mock_response(
                json_data=_commit_detail(
                    item["sha"],
                    "dev",
                    item["commit"]["message"],
                    "2026-09-27T10:00:00Z",
                    1,
                    0,
                    ["f.py"],
                )
            )
        )
    client.request.side_effect = responses

    result = collect(["org/repo-a"], SINCE, UNTIL, client=client, sleep_fn=lambda _: None)

    records = result.records
    assert result.success is True
    assert len(records) == 31
    # 两次列表请求：page=1 和 page=2
    list_calls = [
        call
        for call in client.request.call_args_list
        if call.args[1].endswith("/commits") and "/commits/" not in call.args[1]
    ]
    assert len(list_calls) == 2
    assert list_calls[0].kwargs["params"]["per_page"] == 30
    assert list_calls[0].kwargs["params"]["page"] == 1
    assert list_calls[1].kwargs["params"]["page"] == 2


def test_timeout_retries_three_times_then_returns_empty(caplog):
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = httpx.TimeoutException("timed out")
    sleeps: list[float] = []

    with caplog.at_level("ERROR"):
        result = collect(
            ["org/repo-a"],
            SINCE,
            UNTIL,
            client=client,
            max_retries=3,
            retry_interval=5.0,
            sleep_fn=sleeps.append,
        )

    assert result.success is False
    assert result.records == []
    assert client.request.call_count == 3
    assert sleeps == [5.0, 5.0]
    assert any("GitHub 采集失败" in message for message in caplog.messages)


def test_rate_limit_403_waits_reset_then_retries():
    client = MagicMock(spec=httpx.Client)
    summary = _commit_summary("abc", "lisi", "feat: x", "2026-09-27T12:00:00Z")
    detail = _commit_detail("abc", "lisi", "feat: x", "2026-09-27T12:00:00Z", 5, 1, ["x.py"])

    reset_ts = int(datetime.now(timezone.utc).timestamp()) + 42
    limited = _mock_response(
        status_code=403,
        json_data={"message": "API rate limit exceeded"},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_ts)},
    )
    ok_list = _mock_response(json_data=[summary])
    ok_detail = _mock_response(json_data=detail)
    client.request.side_effect = [limited, ok_list, ok_detail]

    sleeps: list[float] = []
    result = collect(
        ["org/repo-b"],
        SINCE,
        UNTIL,
        client=client,
        sleep_fn=sleeps.append,
    )

    records = result.records
    assert result.success is True
    assert len(records) == 1
    assert records[0].author == "lisi"
    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(42, abs=2)


def test_collect_multiple_repos():
    client = MagicMock(spec=httpx.Client)

    def side_effect(method: str, url: str, params=None):
        if url.endswith("/commits") and "/commits/" not in url:
            repo = url.split("/repos/")[1].split("/commits")[0]
            sha = "sha-a" if repo == "org/a" else "sha-b"
            login = "alice" if repo == "org/a" else "bob"
            return _mock_response(
                json_data=[_commit_summary(sha, login, "msg", "2026-09-27T09:00:00Z")]
            )
        sha = url.rsplit("/", 1)[-1]
        login = "alice" if sha == "sha-a" else "bob"
        return _mock_response(
            json_data=_commit_detail(sha, login, "msg", "2026-09-27T09:00:00Z", 2, 1, ["f.py"])
        )

    client.request.side_effect = side_effect

    result = collect(["org/a", "org/b"], SINCE, UNTIL, client=client, sleep_fn=lambda _: None)

    records = result.records
    assert result.success is True
    assert len(records) == 2
    assert {r.repo for r in records} == {"org/a", "org/b"}
    assert {r.author for r in records} == {"alice", "bob"}
