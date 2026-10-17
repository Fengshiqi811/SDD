"""日报生成：聚合采集数据并输出 Markdown / HTML。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime

from collector.github import CommitRecord
from collector.lark_msg import MessageRecord
from collector.lark_task import TaskRecord
from generator.insights import build_insights
from generator.template import markdown_to_html, render_markdown


@dataclass
class MemberReport:
    """成员日报输入。

    commits/tasks/messages:
    - list[...]  正常采集结果（可为空列表 → 无数据）
    - None       该数据源采集失败 → 日报标注「数据获取失败」
    """

    name: str
    github_username: str
    commits: list[CommitRecord] | None
    tasks: list[TaskRecord] | None
    messages: list[MessageRecord] | None


@dataclass
class DailyReport:
    date: date
    team_name: str
    members: list[MemberReport]
    generated_at: datetime
    markdown: str
    html: str
    insights: dict = field(default_factory=dict)


def build_report_subject(report: DailyReport, *, grade: str | None = None) -> str:
    """按“研一+姓名+日期+智能日报”生成邮件标题。"""
    resolved_grade = (grade if grade is not None else os.getenv("REPORT_GRADE", "研一")).strip()
    member_name = report.members[0].name if report.members else report.team_name
    return f"{resolved_grade}{member_name}{report.date.isoformat()}智能日报"


def generate(
    members: list[MemberReport],
    date: date,
    team_name: str,
    *,
    previous_snapshot: dict | None = None,
    trend: list[dict] | None = None,
    sync: dict | None = None,
    github_activity: dict | None = None,
) -> DailyReport:
    """按「代码提交 → 任务进展 → 协作沟通」组织日报，输出 Markdown 与 HTML。"""
    view_members = [_to_view(member) for member in members]
    insights = build_insights(
        members,
        previous_snapshot=previous_snapshot,
        trend=trend,
        sync=sync,
        github_activity=github_activity,
    )
    markdown = render_markdown(
        team_name=team_name,
        date=date.isoformat(),
        members=view_members,
        insights=insights,
    )
    html = markdown_to_html(markdown)
    return DailyReport(
        date=date,
        team_name=team_name,
        members=members,
        generated_at=datetime.now(),
        markdown=markdown,
        html=html,
        insights=insights,
    )


def _to_view(member: MemberReport) -> dict:
    commits_failed = member.commits is None
    tasks_failed = member.tasks is None
    messages_failed = member.messages is None

    commits = member.commits or []
    tasks = member.tasks or []
    messages = member.messages or []

    has_any_success_data = bool(commits or tasks or messages)
    all_sources_empty = (
        not commits_failed
        and not tasks_failed
        and not messages_failed
        and not has_any_success_data
    )
    # 全部失败且无成功数据时，也视为无有效记录；但若有失败标注则不显示「今日无记录」
    is_empty = all_sources_empty

    return {
        "name": member.name,
        "is_empty": is_empty,
        "commits": commits,
        "tasks": tasks,
        "messages": messages,
        "commits_failed": commits_failed,
        "tasks_failed": tasks_failed,
        "messages_failed": messages_failed,
    }
