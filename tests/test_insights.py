"""日报洞察功能测试。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from collector.github import CommitRecord
from collector.lark_msg import MessageRecord
from collector.lark_task import TaskRecord
from generator.formatter import MemberReport, generate

TS = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)


def _member() -> MemberReport:
    return MemberReport(
        name="冯诗祺",
        github_username="Fengshiqi811",
        commits=[
            CommitRecord(
                author="Fengshiqi811",
                message="feat: 完成日报洞察",
                timestamp=TS,
                repo="Fengshiqi811/SDD",
                additions=10,
                deletions=1,
                files_changed=2,
            )
        ],
        tasks=[
            TaskRecord(
                assignee="ou_test",
                title="完成飞书授权",
                status_from="todo",
                status_to="done",
                updated_at=TS,
                due_at=TS,
            ),
            TaskRecord(
                assignee="ou_test",
                title="处理阻塞风险",
                status_from="todo",
                status_to="in_progress",
                updated_at=TS,
            ),
        ],
        messages=[
            MessageRecord(
                sender="ou_test",
                sender_name="冯诗祺",
                content="完成飞书授权",
                timestamp=TS,
                chat_name="日报测试",
            )
        ],
    )


def test_generate_builds_metrics_ai_summary_and_priority():
    report = generate([_member()], date(2026, 10, 13), "智能日报")
    insights = report.insights

    assert insights["metrics"]["completed"]["count"] == 2
    assert insights["metrics"]["in_progress"]["count"] == 1
    assert insights["metrics"]["important"]["count"] >= 1
    assert insights["ai_summary"]
    assert any(item["priority"] == "高" for item in insights["important_items"])
    assert "AI 今日总结" in report.markdown
    assert "今日概览" in report.markdown
    assert "重点事项与下一步" in report.markdown


def test_insights_deduplicates_task_notification_message():
    report = generate([_member()], date(2026, 10, 13), "智能日报")
    message_items = [
        item for item in report.insights["timeline"] if item["source"] == "飞书消息"
    ]
    assert message_items == []