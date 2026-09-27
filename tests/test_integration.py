"""端到端集成测试（mock 采集/推送）— Task 10。"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from collector.github import CommitRecord
from collector.lark_msg import MessageRecord
from collector.lark_task import TaskRecord
from collector.result import CollectResult
from main import run_pipeline
from shared.config import (
    AppConfig,
    EmailNotifierConfig,
    GitHubConfig,
    LarkBotConfig,
    LarkConfig,
    MemberConfig,
    NotifierConfig,
)
from shared.storage import ReportStorage

TS = datetime(2026, 9, 27, 10, 0, 0, tzinfo=timezone.utc)


def _config(members: list[MemberConfig] | None = None) -> AppConfig:
    return AppConfig(
        team_name="研发团队",
        members=members
        or [
            MemberConfig(name="张三", github="zhangsan", lark="zhangsan@company.com"),
            MemberConfig(name="李四", github="lisi-dev", lark="lisi@company.com"),
        ],
        github=GitHubConfig(repos=["org/repo-a"]),
        lark=LarkConfig(project_id="proj-1", chat_id="chat-1", keywords=["进度"]),
        notifier=NotifierConfig(
            email=EmailNotifierConfig(recipients=["leader@company.com"]),
            lark_bot=LarkBotConfig(chat_id="notify-chat"),
        ),
    )


@pytest.fixture
def storage(tmp_path):
    return ReportStorage(tmp_path / "reports.db")


def test_normal_flow_generates_and_pushes(storage, caplog):
    """正常场景：所有数据源可用，日报生成并推送成功。"""
    config = _config()
    github_result = CollectResult(
        success=True,
        records=[
            CommitRecord(
                author="zhangsan",
                message="feat: login",
                timestamp=TS,
                repo="org/repo-a",
                additions=10,
                deletions=1,
                files_changed=1,
            )
        ],
    )
    task_result = CollectResult(
        success=True,
        records=[
            TaskRecord(
                assignee="zhangsan@company.com",
                title="完成登录",
                status_from="todo",
                status_to="done",
                updated_at=TS,
            )
        ],
    )
    msg_result = CollectResult(
        success=True,
        records=[
            MessageRecord(
                sender="zhangsan@company.com",
                content="进度正常",
                timestamp=TS,
                chat_name="研发群",
            )
        ],
    )

    with (
        patch("main.github_collector.collect", return_value=github_result),
        patch("main.lark_task_collector.collect", return_value=task_result),
        patch("main.lark_msg_collector.collect", return_value=msg_result),
        patch("main.email_notifier.send", return_value=True) as email_send,
        patch("main.lark_bot_notifier.send", return_value=True) as lark_send,
        patch("main.ReportStorage", return_value=storage),
        caplog.at_level("INFO"),
    ):
        started = time.perf_counter()
        code = run_pipeline(config, dry_run=False)
        elapsed = time.perf_counter() - started

    assert code == 0
    assert elapsed < 60
    assert email_send.called
    assert lark_send.called
    report = email_send.call_args.args[0]
    assert "代码提交" in report.markdown
    assert "feat: login" in report.markdown
    assert "完成登录" in report.markdown
    assert "进度正常" in report.markdown
    assert any("推送结果" in m for m in caplog.messages)
    assert storage.get_report(report.date, "研发团队") is not None


def test_degraded_source_marks_failure_and_continues(storage, caplog):
    """降级场景：某个数据源失败，日报标注「数据获取失败」，其他部分正常。"""
    config = _config(
        members=[MemberConfig(name="张三", github="zhangsan", lark="zhangsan@company.com")]
    )
    github_failed = CollectResult(success=False, records=[], error_message="timeout")
    task_ok = CollectResult(
        success=True,
        records=[
            TaskRecord(
                assignee="zhangsan@company.com",
                title="联调接口",
                status_from="todo",
                status_to="done",
                updated_at=TS,
            )
        ],
    )
    msg_ok = CollectResult(
        success=True,
        records=[
            MessageRecord(
                sender="zhangsan@company.com",
                content="进度同步",
                timestamp=TS,
                chat_name="研发群",
            )
        ],
    )

    with (
        patch("main.github_collector.collect", return_value=github_failed),
        patch("main.lark_task_collector.collect", return_value=task_ok),
        patch("main.lark_msg_collector.collect", return_value=msg_ok),
        patch("main.email_notifier.send", return_value=True) as email_send,
        patch("main.lark_bot_notifier.send", return_value=True),
        patch("main.ReportStorage", return_value=storage),
        caplog.at_level("INFO"),
    ):
        code = run_pipeline(config, dry_run=False)

    assert code == 0
    assert email_send.called
    md = email_send.call_args.args[0].markdown
    assert "数据获取失败" in md
    assert "联调接口" in md
    assert "进度同步" in md
    assert "代码提交" in md


def test_empty_member_shows_no_records_today(storage):
    """空数据场景：某成员无任何记录，显示「今日无记录」（仍生成日报）。"""
    config = _config(
        members=[
            MemberConfig(name="张三", github="zhangsan", lark="zhangsan@company.com"),
            MemberConfig(name="李四", github="lisi-dev", lark="lisi@company.com"),
        ]
    )
    # 仅张三有数据；李四三源皆空 → 「今日无记录」
    github_result = CollectResult(
        success=True,
        records=[
            CommitRecord(
                author="zhangsan",
                message="fix: npe",
                timestamp=TS,
                repo="org/repo-a",
                additions=2,
                deletions=0,
                files_changed=1,
            )
        ],
    )
    empty_ok = CollectResult(success=True, records=[])

    with (
        patch("main.github_collector.collect", return_value=github_result),
        patch("main.lark_task_collector.collect", return_value=empty_ok),
        patch("main.lark_msg_collector.collect", return_value=empty_ok),
        patch("main.email_notifier.send", return_value=True) as email_send,
        patch("main.lark_bot_notifier.send", return_value=True),
        patch("main.ReportStorage", return_value=storage),
    ):
        code = run_pipeline(config, dry_run=False)

    assert code == 0
    md = email_send.call_args.args[0].markdown
    assert "李四" in md
    assert "今日无记录" in md
    assert "fix: npe" in md


def test_all_sources_failed_no_report_no_push(storage, caplog):
    """全部失败场景：不生成日报、不推送，只记录错误日志。"""
    config = _config()
    failed = CollectResult(success=False, records=[], error_message="unavailable")

    with (
        patch("main.github_collector.collect", return_value=failed),
        patch("main.lark_task_collector.collect", return_value=failed),
        patch("main.lark_msg_collector.collect", return_value=failed),
        patch("main.email_notifier.send") as email_send,
        patch("main.lark_bot_notifier.send") as lark_send,
        patch("main.ReportStorage", return_value=storage),
        caplog.at_level("ERROR"),
    ):
        started = time.perf_counter()
        code = run_pipeline(config, dry_run=False)
        elapsed = time.perf_counter() - started

    assert code == 1
    assert elapsed < 60
    assert not email_send.called
    assert not lark_send.called
    assert storage.list_reports() == []
    assert any("所有数据源采集失败" in m for m in caplog.messages)


def test_integration_suite_under_60_seconds(storage):
    """mock 环境下四场景总耗时应远小于 60 秒。"""
    config = _config(
        members=[MemberConfig(name="张三", github="zhangsan", lark="zhangsan@company.com")]
    )
    ok = CollectResult(success=True, records=[])
    failed = CollectResult(success=False, records=[], error_message="x")

    started = time.perf_counter()
    with (
        patch("main.email_notifier.send", return_value=True),
        patch("main.lark_bot_notifier.send", return_value=True),
        patch("main.ReportStorage", return_value=storage),
    ):
        with (
            patch("main.github_collector.collect", return_value=ok),
            patch("main.lark_task_collector.collect", return_value=ok),
            patch("main.lark_msg_collector.collect", return_value=ok),
        ):
            run_pipeline(config, dry_run=False)
        with (
            patch("main.github_collector.collect", return_value=failed),
            patch("main.lark_task_collector.collect", return_value=ok),
            patch("main.lark_msg_collector.collect", return_value=ok),
        ):
            run_pipeline(config, dry_run=False)
        with (
            patch("main.github_collector.collect", return_value=failed),
            patch("main.lark_task_collector.collect", return_value=failed),
            patch("main.lark_msg_collector.collect", return_value=failed),
        ):
            run_pipeline(config, dry_run=False)
    assert time.perf_counter() - started < 60
