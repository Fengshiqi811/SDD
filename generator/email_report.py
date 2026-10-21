"""生成绿色表格样式的真实日报邮件 HTML。"""

from __future__ import annotations

import html
import os
from typing import Any, Iterable

GREEN_CSS = """
body { font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.7; color: #222; }
h1 { color: #1b5e20; }
h2 { margin-top: 24px; color: #2e7d32; border-bottom: 1px solid #c8e6c9; padding-bottom: 4px; }
h3 { color: #246f46; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th, td { border: 1px solid #bfbfbf; padding: 8px; text-align: left; vertical-align: top; }
th { background: #e8f5e9; }
li { margin-bottom: 6px; }
.metric-table { width: 100%; border-collapse: separate; border-spacing: 8px 0; }
.metric-card { width: 25%; padding: 12px; border: 1px solid #81c784; background: #f1f8e9; border-radius: 6px; text-align: center; vertical-align: top; }
.metric-card .value { display: block; font-size: 24px; font-weight: bold; color: #1b5e20; }
.metric-card .label { display: block; font-size: 13px; color: #555; }
.note { color: #666; font-size: 13px; }
"""


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _status(value: Any) -> str:
    text = str(value or "").lower()
    return {
        "done": "已完成",
        "completed": "已完成",
        "in_progress": "进行中",
        "doing": "进行中",
        "todo": "待处理",
        "unknown": "待处理",
    }.get(text, text or "待处理")


def _titles(items: Iterable[dict[str, Any]], empty: str = "无") -> str:
    values = [f"<strong>{_e(item.get('title'))}</strong>" for item in items if item.get("title")]
    return "；".join(values) if values else empty


def _metric_card(label: str, metric: dict[str, Any]) -> str:
    delta = int(metric.get("delta", 0) or 0)
    delta_text = "较昨日无变化" if delta == 0 else f"较昨日 {delta:+d}"
    return (
        '<td class="metric-card">'
        f'<span class="value">{int(metric.get("count", 0) or 0)}</span>'
        f'<span class="label">{_e(label)}</span>'
        f'<span class="label">{_e(delta_text)}</span>'
        "</td>"
    )

def render_email_html(report: Any) -> str:
    """根据真实采集结果和洞察生成绿色表格化邮件正文。"""
    insights = getattr(report, "insights", {}) or {}
    metrics = insights.get("metrics", {}) or {}
    ai_summary = insights.get("ai_summary", []) or []
    changes = insights.get("changes", {}) or {}
    deadlines = insights.get("deadlines", {}) or {}
    activity = insights.get("github_activity", {}) or {}
    sync = insights.get("sync", {}) or {}
    important_items = insights.get("important_items", []) or []
    timeline = insights.get("timeline", []) or []
    member = report.members[0] if report.members else None
    member_name = member.name if member else report.team_name
    grade = os.getenv("REPORT_GRADE", "研一").strip() or "研一"
    title = f"{grade}{member_name}{report.date.isoformat()}智能日报"

    tasks = [task for m in report.members for task in (m.tasks or [])]
    messages = [message for m in report.members for message in (m.messages or [])]
    commits = [commit for m in report.members for commit in (m.commits or [])]
    failed_sources = [
        name
        for name, state in (sync.get("source_status", {}) or {}).items()
        if isinstance(state, dict) and not state.get("success", True)
    ]
    source_state = "部分数据源失败" if failed_sources else "数据源采集成功"

    ai_html = "".join(f"<li>{_e(line)}</li>" for line in ai_summary) or "<li>暂无总结</li>"
    metric_html = (
        '<table class="metric-table"><tr>'
        + _metric_card("今日完成任务数", metrics.get("completed", {}))
        + _metric_card("进行中任务数", metrics.get("in_progress", {}))
        + _metric_card("待处理任务数", metrics.get("pending", {}))
        + _metric_card("今日重要事项数", metrics.get("important", {}))
        + "</tr></table>"
    )

    change_rows = [
        ("新增", _titles(changes.get("added", []))),
        ("已完成", _titles(changes.get("completed", []))),
        ("进行中", _titles(changes.get("in_progress", []))),
        ("阻塞", _titles(changes.get("blocked", []))),
        (
            "持续无变化",
            "；".join(
                f"{_e(item.get('title'))}（连续 {int(item.get('days', 0) or 0)} 天）"
                for item in changes.get("stale", [])
            )
            or "无",
        ),
    ]
    change_html = "".join(f"<tr><td>{name}</td><td>{value}</td></tr>" for name, value in change_rows)

    trend_rows = "".join(
        f"<tr><td>{_e(item.get('date'))}</td><td>{int(item.get('completed', 0) or 0)}</td>"
        f"<td>{int(item.get('in_progress', 0) or 0)}</td><td>{int(item.get('pending', 0) or 0)}</td></tr>"
        for item in changes.get("trend", [])
    ) or '<tr><td colspan="4">暂无趋势数据</td></tr>'

    deadline_html = "".join(
        f"<tr><td>{label}</td><td>{len(deadlines.get(key, []) or [])}</td><td>{_titles(deadlines.get(key, []))}</td></tr>"
        for label, key in [
            ("已逾期", "overdue"),
            ("今日到期", "due_today"),
            ("未来 3 天到期", "due_next_3_days"),
            ("长期未更新", "stale_unupdated"),
            ("缺少截止日期", "missing_due"),
        ]
    )

    counts = activity.get("counts", {}) or {}
    prs = activity.get("pull_requests", []) or []
    issues = activity.get("issues", []) or []
    reviews = activity.get("reviews", []) or []
    github_rows = [
        ("提交 Commit", len(commits) or int(counts.get("commits", 0) or 0), "本期新增提交"),
        ("Pull Request", int(counts.get("pull_requests", len(prs)) or 0), "本期 PR 活动"),
        ("Issue", int(counts.get("issues", len(issues)) or 0), "本期 Issue 活动"),
        ("代码评审", int(counts.get("reviews", len(reviews)) or 0), "本期评审活动"),
    ]
    github_html = "".join(f"<tr><td>{name}</td><td>{count}</td><td>{_e(note)}</td></tr>" for name, count, note in github_rows)
    commit_html = "".join(
        f"<li><strong>{_e(commit.repo)}</strong>：{_e(commit.message)}（{_e(commit.timestamp.isoformat())}）</li>"
        for commit in commits
    ) or "<li>本期无提交</li>"
    pr_html = "".join(
        f"<li>PR #{_e(item.get('number'))} {_e(item.get('title'))}（{_e(item.get('state'))}）</li>"
        for item in prs
    ) or "<li>本期无新增 PR</li>"
    issue_html = "".join(
        f"<li>Issue #{_e(item.get('number'))} {_e(item.get('title'))}（{_e(item.get('state'))}）</li>"
        for item in issues
    ) or "<li>本期无新增 Issue</li>"
    review_html = "".join(
        f"<li>评审 PR #{_e(item.get('number'))} {_e(item.get('title'))}</li>"
        for item in reviews
    ) or "<li>本期无代码评审</li>"

    important_html = "".join(
        "<tr>"
        f"<td>{_e(item.get('priority'))}</td><td>{_e(item.get('title'))}</td>"
        f"<td>{_e(item.get('status'))}</td><td>{_e(item.get('source'))}</td>"
        f"<td>{_e(item.get('due') or '未设置')}</td><td>{_e(item.get('next_action') or '无')}</td>"
        "</tr>"
        for item in important_items
    ) or '<tr><td colspan="6">暂无重点事项</td></tr>'

    task_html = "".join(
        f"<tr><td>{_e(task.title)}</td><td>{_e(_status(task.status_from))} → {_e(_status(task.status_to))}</td>"
        f"<td>{_e(task.assignee)}</td></tr>"
        for task in tasks
    ) or "<tr><td colspan=\"3\">今日无任务记录</td></tr>"
    message_html = "".join(
        f"<tr><td>{_e(message.sender_name or message.sender)}</td><td>{_e(message.content)}</td><td>{_e(message.chat_name)}</td></tr>"
        for message in messages
    ) or "<tr><td colspan=\"3\">今日无协作消息</td></tr>"

    source_html = "".join(
        f"<tr><td>{_e(name)}</td><td>{'成功' if state.get('success') else '失败'}</td><td>{_e(state.get('error') or '—')}</td></tr>"
        for name, state in (sync.get("source_status", {}) or {}).items()
        if isinstance(state, dict)
    ) or "<tr><td colspan=\"3\">暂无同步状态</td></tr>"
    next_actions = []
    for item in important_items:
        if item.get("status") != "已完成" and item.get("next_action"):
            next_actions.append(item["next_action"])
    if not next_actions:
        next_actions = ["继续积累飞书任务与 GitHub 提交数据。", "持续关注任务截止时间与科研产出。"]
    next_html = "".join(f"<li>{_e(action)}</li>" for action in list(dict.fromkeys(next_actions))[:5])
    timeline_html = "".join(
        f"<li>[{_e(item.get('source'))}] {_e(item.get('title'))}（{_e(item.get('status'))}）</li>"
        for item in timeline[:20]
    ) or "<li>暂无工作产出记录</li>"

    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
        '<style>' + GREEN_CSS + '</style></head><body>'
        f'<h1>{_e(title)}</h1>'
        f'<p><strong>汇报人：</strong>{_e(member_name)}　　　'
        f'<strong>生成日期：</strong>{_e(report.date.isoformat())}　　　'
        f'<strong>数据范围：</strong>{_e(sync.get("time_range") or "未知")}</p>'
        '<h2>一、AI 今日总结</h2>'
        f'<ol>{ai_html}</ol>'
        '<h2>二、关键指标</h2>'
        f'{metric_html}'
        '<h2>三、每日变化对比</h2>'
        '<table><thead><tr><th>变化类型</th><th>具体内容</th></tr></thead><tbody>'
        f'{change_html}</tbody></table>'
        '<h2>四、近 7 天任务趋势</h2>'
        '<table><thead><tr><th>日期</th><th>完成任务</th><th>进行中</th><th>待处理</th></tr></thead><tbody>'
        f'{trend_rows}</tbody></table>'
        '<h2>五、截止日期与风险预警</h2>'
        '<table><thead><tr><th>预警类型</th><th>数量</th><th>具体事项</th></tr></thead><tbody>'
        f'{deadline_html}</tbody></table>'
        '<h2>六、GitHub 科研代码追踪</h2>'
        '<table><thead><tr><th>活动类型</th><th>数量</th><th>说明</th></tr></thead><tbody>'
        f'{github_html}</tbody></table>'
        '<h3>代码提交</h3><ul>' + commit_html + '</ul>'
        '<h3>Pull Request 明细</h3><ul>' + pr_html + '</ul>'
        '<h3>Issue 明细</h3><ul>' + issue_html + '</ul>'
        '<h3>代码评审明细</h3><ul>' + review_html + '</ul>'
        '<h2>七、重点事项与下一步</h2>'
        '<table><thead><tr><th>优先级</th><th>事项</th><th>状态</th><th>来源</th><th>截止时间</th><th>下一步</th></tr></thead><tbody>'
        f'{important_html}</tbody></table>'
        '<h2>八、任务与协作明细</h2>'
        '<h3>飞书任务</h3><table><thead><tr><th>任务</th><th>状态变化</th><th>负责人</th></tr></thead><tbody>'
        f'{task_html}</tbody></table>'
        '<h3>协作沟通</h3><table><thead><tr><th>发送人</th><th>内容</th><th>群聊</th></tr></thead><tbody>'
        f'{message_html}</tbody></table>'
        '<h2>九、工作产出与项目进展</h2><ul>' + timeline_html + '</ul>'
        '<h2>十、数据同步状态</h2>'
        f'<p class="note">{_e(source_state)}；最后同步时间：{_e(sync.get("last_synced") or "未知")}</p>'
        '<table><thead><tr><th>数据源</th><th>状态</th><th>说明</th></tr></thead><tbody>'
        f'{source_html}</tbody></table>'
        '<h2>十一、下一步行动</h2><ol>' + next_html + '</ol>'
        '<p class="note">本日报由智能日报系统根据飞书任务、飞书群消息和 GitHub 活动自动生成。</p>'
        '</body></html>'
    )
