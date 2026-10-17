"""网页接口测试：飞书数据进入日报，发送时由后端自动生成。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from collector.github import CommitRecord
from collector.lark_msg import MessageRecord
from collector.lark_task import TaskRecord
from collector.result import CollectResult
from main import app
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

TS = datetime(2026, 10, 11, 4, 0, 0, tzinfo=timezone.utc)


def _config() -> AppConfig:
    return AppConfig(
        team_name="智能日报",
        members=[
            MemberConfig(
                name="冯诗祺",
                github="fengshiqi",
                lark="fengshiqi@example.com",
            )
        ],
        github=GitHubConfig(repos=["org/repo"]),
        lark=LarkConfig(
            project_id="project-id",
            chat_id="chat-id",
            keywords=["进度"],
        ),
        notifier=NotifierConfig(
            email=EmailNotifierConfig(recipients=[]),
            lark_bot=LarkBotConfig(chat_id="notify-chat"),
        ),
    )


def _results():
    return (
        CollectResult(
            success=True,
            records=[
                CommitRecord(
                    author="fengshiqi",
                    message="feat: 接入飞书任务",
                    timestamp=TS,
                    repo="org/repo",
                    additions=12,
                    deletions=2,
                    files_changed=2,
                )
            ],
        ),
        CollectResult(
            success=True,
            records=[
                TaskRecord(
                    assignee="fengshiqi@example.com",
                    title="完成飞书任务同步",
                    status_from="in_progress",
                    status_to="done",
                    updated_at=TS,
                )
            ],
        ),
        CollectResult(
            success=True,
            records=[
                MessageRecord(
                    sender="fengshiqi@example.com",
                    content="进度同步：飞书消息已接入日报",
                    timestamp=TS,
                    chat_name="研发群",
                )
            ],
        ),
    )


def test_report_api_uses_lark_task_and_message_data(tmp_path, monkeypatch):
    github_result, task_result, message_result = _results()
    storage = ReportStorage(tmp_path / "reports.db")

    with (
        patch("main.load_runtime_config", return_value=_config()),
        patch("main.github_collector.collect", return_value=github_result),
        patch("main.lark_task_collector.collect", return_value=task_result),
        patch("main.lark_msg_collector.collect", return_value=message_result),
        patch("main.ReportStorage", return_value=storage),
    ):
        response = app.test_client().post(
            "/api/report",
            json={"date": "2026-10-11", "member": "冯诗祺"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 0
    assert "完成飞书任务同步" in payload["data"]
    assert "飞书消息已接入日报" in payload["data"]
    assert payload["raw"]["lark_task"][0]["title"] == "完成飞书任务同步"
    assert payload["raw"]["lark_msg"][0]["content"] == "进度同步：飞书消息已接入日报"


def test_send_report_api_regenerates_before_sending(tmp_path):
    github_result, task_result, message_result = _results()
    storage = ReportStorage(tmp_path / "reports.db")
    sent: dict[str, object] = {}

    def capture_send(report, recipient):
        sent["report"] = report
        sent["recipient"] = recipient

    with (
        patch("main.load_runtime_config", return_value=_config()),
        patch("main.github_collector.collect", return_value=github_result),
        patch("main.lark_task_collector.collect", return_value=task_result),
        patch("main.lark_msg_collector.collect", return_value=message_result),
        patch("main.ReportStorage", return_value=storage),
        patch("main._send_report_email", side_effect=capture_send),
    ):
        response = app.test_client().post(
            "/api/send-report",
            json={
                "to_email": "teacher@example.com",
                "date": "2026-10-11",
                "member": "冯诗祺",
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 0
    assert sent["recipient"] == "teacher@example.com"
    assert "完成飞书任务同步" in sent["report"].markdown
    assert "飞书消息已接入日报" in sent["report"].markdown
    assert sent["report"].markdown == payload["data"]