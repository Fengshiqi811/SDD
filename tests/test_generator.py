"""generator 日报生成模块单元测试（mock 数据）— TDD 先红后绿。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from collector.github import CommitRecord
from collector.lark_msg import MessageRecord
from collector.lark_task import TaskRecord
from generator.formatter import DailyReport, MemberReport, generate

REPORT_DATE = date(2026, 9, 27)
TEAM = "研发团队"
TS = datetime(2026, 9, 27, 10, 0, 0, tzinfo=timezone.utc)


def _commit(message: str = "fix: login") -> CommitRecord:
    return CommitRecord(
        author="zhangsan",
        message=message,
        timestamp=TS,
        repo="org/repo-a",
        additions=10,
        deletions=2,
        files_changed=1,
    )


def _task(title: str = "完成登录页") -> TaskRecord:
    return TaskRecord(
        assignee="zhangsan@company.com",
        title=title,
        status_from="todo",
        status_to="done",
        updated_at=TS,
    )


def _message(content: str = "进度同步") -> MessageRecord:
    return MessageRecord(
        sender="zhangsan@company.com",
        content=content,
        timestamp=TS,
        chat_name="研发群",
    )


def test_generate_signature_and_three_section_titles():
    members = [
        MemberReport(
            name="张三",
            github_username="zhangsan",
            commits=[_commit()],
            tasks=[_task()],
            messages=[_message()],
        )
    ]

    report = generate(members, REPORT_DATE, TEAM)

    assert isinstance(report, DailyReport)
    assert report.date == REPORT_DATE
    assert report.team_name == TEAM
    assert report.members == members
    assert isinstance(report.generated_at, datetime)

    md = report.markdown
    assert "代码提交" in md
    assert "任务进展" in md
    assert "协作沟通" in md
    # 顺序：代码提交 → 任务进展 → 协作沟通
    assert md.index("代码提交") < md.index("任务进展") < md.index("协作沟通")


def test_empty_member_shows_no_records_today():
    members = [
        MemberReport(
            name="李四",
            github_username="lisi-dev",
            commits=[],
            tasks=[],
            messages=[],
        )
    ]

    report = generate(members, REPORT_DATE, TEAM)

    assert "今日无记录" in report.markdown
    assert "李四" in report.markdown


def test_failed_data_source_marked_as_fetch_failed():
    # None 表示该数据源采集失败（与空列表「无数据」区分）
    members = [
        MemberReport(
            name="王五",
            github_username="wangwu",
            commits=None,
            tasks=[_task("联调接口")],
            messages=None,
        )
    ]

    report = generate(members, REPORT_DATE, TEAM)
    md = report.markdown

    assert "数据获取失败" in md
    assert md.count("数据获取失败") >= 2  # commits + messages
    assert "联调接口" in md
    assert "今日无记录" not in md


def test_markdown_to_html_conversion():
    members = [
        MemberReport(
            name="张三",
            github_username="zhangsan",
            commits=[_commit("feat: dashboard")],
            tasks=[],
            messages=[],
        )
    ]

    report = generate(members, REPORT_DATE, TEAM)

    html = report.html
    assert "<html" in html.lower() or "<h1" in html.lower() or "<h2" in html.lower()
    assert "代码提交" in html
    assert "feat: dashboard" in html
    # 基本可渲染结构
    assert "<ul>" in html or "<li>" in html or "<p>" in html


def test_aggregates_commit_and_task_into_markdown():
    members = [
        MemberReport(
            name="张三",
            github_username="zhangsan",
            commits=[_commit("fix: NPE"), _commit("docs: readme")],
            tasks=[_task("修复崩溃"), _task("更新文档")],
            messages=[_message("评审已通过")],
        )
    ]

    report = generate(members, REPORT_DATE, TEAM)
    md = report.markdown

    assert "fix: NPE" in md
    assert "docs: readme" in md
    assert "修复崩溃" in md
    assert "更新文档" in md
    assert "评审已通过" in md
    assert "org/repo-a" in md
