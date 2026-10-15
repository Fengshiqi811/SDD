"""日报洞察：指标、重点排序、变化对比、待办提取和 AI 摘要。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable

HIGH_PRIORITY_KEYWORDS = (
    "阻塞", "风险", "紧急", "延期", "失败", "报错", "截止", "上线", "故障", "事故",
)
MEDIUM_PRIORITY_KEYWORDS = (
    "评审", "联调", "提交", "进度", "测试", "会议", "安排", "跟进", "完成", "发布",
)
ACTION_KEYWORDS = (
    "需要", "待办", "待处理", "跟进", "安排", "提交", "完善", "修复", "核对", "确认",
)
BLOCKED_KEYWORDS = ("阻塞", "卡住", "失败", "报错", "风险", "延期")


def _normalize(text: str) -> str:
    return "".join((text or "").split()).lower()


def _text_of(value: Any) -> str:
    return str(value or "").strip()


def _priority(text: str) -> tuple[str, int]:
    value = _text_of(text)
    if any(keyword in value for keyword in HIGH_PRIORITY_KEYWORDS):
        return "高", 5
    if any(keyword in value for keyword in MEDIUM_PRIORITY_KEYWORDS):
        return "中", 3
    return "低", 2


def _task_status(status_to: str) -> str:
    status = _text_of(status_to).lower()
    if status in {"done", "completed", "complete"}:
        return "已完成"
    if status in {"in_progress", "doing", "processing"}:
        return "进行中"
    if status in {"blocked", "block"}:
        return "已阻塞"
    return "待处理"


def _next_action(status: str, priority: str) -> str:
    if status == "已完成":
        return ""
    if status == "已阻塞" or priority == "高":
        return "立即协调解决并明确负责人"
    if status == "进行中":
        return "继续推进并同步最新进展"
    return "安排时间推进"


def _parse_due(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_activity_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _risk_level(item: dict[str, Any], today: date) -> str:
    due = _parse_due(item.get("due", ""))
    status = item.get("status")
    priority = item.get("priority")
    if status == "已完成":
        return "低"
    if due is not None:
        days = (due - today).days
        if days < 0:
            return "高"
        if days <= 1 and priority in {"高", "中"}:
            return "高"
        if days <= 3:
            return "中"
    if status == "已阻塞" or priority == "高":
        return "高"
    if priority == "中":
        return "中"
    return "低"


def _item_common(
    *,
    title: str,
    source: str,
    status: str,
    timestamp: datetime | None = None,
    owner: str = "",
    due: str = "",
    detail: str = "",
) -> dict[str, Any]:
    priority, score = _priority(f"{title} {detail}")
    return {
        "title": title.strip(),
        "source": source,
        "priority": priority,
        "score": score,
        "status": status,
        "owner": owner,
        "due": due,
        "next_action": _next_action(status, priority),
        "detail": detail.strip(),
        "time": timestamp.isoformat() if timestamp else "",
    }


def _dedupe_tasks(tasks: Iterable[Any]) -> list[Any]:
    seen: set[str] = set()
    result = []
    for task in tasks:
        key = _normalize(getattr(task, "title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(task)
    return result


def _dedupe_messages(messages: Iterable[Any], task_titles: set[str]) -> list[Any]:
    seen: set[str] = set()
    result = []
    for message in messages:
        key = _normalize(getattr(message, "content", ""))
        if not key or key in seen or key in task_titles:
            continue
        seen.add(key)
        result.append(message)
    return result

def _collect_items(members: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_titles: set[str] = set()
    for member in members:
        for task in member.tasks or []:
            task_titles.add(_normalize(getattr(task, "title", "")))

    items: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []

    for member in members:
        for task in _dedupe_tasks(member.tasks or []):
            item = _item_common(
                title=_text_of(getattr(task, "title", "")),
                source="飞书任务",
                status=_task_status(getattr(task, "status_to", "")),
                timestamp=getattr(task, "updated_at", None),
                owner=getattr(task, "assignee", ""),
                due=(
                    getattr(task, "due_at", None).isoformat()
                    if getattr(task, "due_at", None)
                    else ""
                ),
            )
            items.append(item)
            timeline.append(item)

        for message in _dedupe_messages(member.messages or [], task_titles):
            content = _text_of(getattr(message, "content", ""))
            status = "已阻塞" if any(k in content for k in BLOCKED_KEYWORDS) else (
                "待处理" if any(k in content for k in ACTION_KEYWORDS) else "信息"
            )
            item = _item_common(
                title=content,
                source="飞书消息",
                status=status,
                timestamp=getattr(message, "timestamp", None),
                owner=getattr(message, "sender_name", "") or getattr(message, "sender", ""),
                detail=getattr(message, "chat_name", ""),
            )
            items.append(item)
            timeline.append(item)

        for commit in member.commits or []:
            item = _item_common(
                title=_text_of(getattr(commit, "message", "")),
                source="GitHub",
                status="已完成",
                timestamp=getattr(commit, "timestamp", None),
                owner=getattr(commit, "author", ""),
                detail=getattr(commit, "repo", ""),
            )
            items.append(item)
            timeline.append(item)

    timeline.sort(key=lambda item: item.get("time") or "", reverse=True)
    return items, timeline


def build_insights(
    members: list[Any],
    *,
    report_date: date | None = None,
    previous_snapshot: dict[str, Any] | None = None,
    trend: list[dict[str, Any]] | None = None,
    sync: dict[str, Any] | None = None,
    github_activity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从成员采集结果生成结构化日报洞察。"""
    items, timeline = _collect_items(members)
    activity = github_activity or {}
    for record in activity.get("pull_requests", []):
        state = str(record.get("state") or "").lower()
        status = "已完成" if state in {"closed", "merged"} else "进行中"
        item = _item_common(
            title=f"PR #{record.get('number')} {record.get('title', '')}".strip(),
            source="GitHub PR",
            status=status,
            timestamp=_parse_activity_time(record.get("updated_at")),
            detail=f"{record.get('repo', '')} {record.get('branch', '')}".strip(),
        )
        items.append(item)
        timeline.append(item)
    for record in activity.get("issues", []):
        state = str(record.get("state") or "").lower()
        status = "已完成" if state == "closed" else "待处理"
        item = _item_common(
            title=f"Issue #{record.get('number')} {record.get('title', '')}".strip(),
            source="GitHub Issue",
            status=status,
            timestamp=_parse_activity_time(record.get("updated_at")),
            detail=str(record.get("repo") or ""),
        )
        items.append(item)
        timeline.append(item)
    for record in activity.get("reviews", []):
        item = _item_common(
            title=f"评审 PR #{record.get('number')} {record.get('title', '')}".strip(),
            source="GitHub 评审",
            status="已完成",
            timestamp=_parse_activity_time(record.get("updated_at")),
            detail=str(record.get("repo") or ""),
        )
        items.append(item)
        timeline.append(item)
    today = report_date or date.today()
    for item in items:
        item["risk"] = _risk_level(item, today)
    completed = [item for item in items if item["status"] == "已完成"]
    in_progress = [item for item in items if item["status"] == "进行中"]
    blocked = [item for item in items if item["status"] == "已阻塞"]
    pending = [item for item in items if item["status"] == "待处理"]
    important_items = [item for item in items if item["priority"] in {"高", "中"}]
    important_items.sort(key=lambda item: (-item["score"], item["status"] != "待处理"))

    overdue: list[dict[str, Any]] = []
    due_today: list[dict[str, Any]] = []
    due_next_3_days: list[dict[str, Any]] = []
    missing_due: list[dict[str, Any]] = []
    stale_unupdated: list[dict[str, Any]] = []
    for item in items:
        if item["source"] not in {"飞书任务", "GitHub PR", "GitHub Issue"}:
            continue
        if item["status"] == "已完成":
            continue
        due = _parse_due(item.get("due", ""))
        if due is None:
            if item["priority"] in {"高", "中"}:
                missing_due.append(item)
        else:
            days = (due - today).days
            if days < 0:
                overdue.append(item)
            elif days == 0:
                due_today.append(item)
            elif days <= 3:
                due_next_3_days.append(item)
        if item.get("time"):
            try:
                updated = datetime.fromisoformat(item["time"].replace("Z", "+00:00"))
                if updated.tzinfo is not None:
                    updated = updated.astimezone().replace(tzinfo=None)
                if today - updated.date() >= timedelta(days=3):
                    stale_unupdated.append(item)
            except ValueError:
                pass

    previous = previous_snapshot or {}
    previous_keys = set(previous.get("item_keys", []))
    previous_pending = set(previous.get("pending_keys", []))
    previous_completed = set(previous.get("completed_keys", []))
    stale_counts = dict(previous.get("stale_counts", {}))

    def key_of(item: dict[str, Any]) -> str:
        return f"{item['source']}:{_normalize(item['title'])}"

    current_keys = {key_of(item) for item in items}
    current_pending = {key_of(item) for item in pending}
    current_completed = {key_of(item) for item in completed}
    added_keys = current_keys - previous_keys
    stale_keys = current_pending & previous_pending
    stale = []
    for item in pending:
        key = key_of(item)
        if key in stale_keys:
            count = int(stale_counts.get(key, 1)) + 1
            stale_counts[key] = count
            stale.append({"title": item["title"], "days": count, "source": item["source"]})

    changes = {
        "added": [item for item in items if key_of(item) in added_keys],
        "completed": [item for item in completed if key_of(item) not in previous_completed],
        "in_progress": in_progress,
        "blocked": blocked,
        "unchanged": [
            item
            for item in items
            if key_of(item) in previous_keys and key_of(item) not in added_keys
        ],
        "stale": stale,
        "trend": list(trend or []),
    }

    metrics = {
        "completed": {
            "count": len(completed),
            "delta": len(completed) - int(previous.get("completed_count", 0)),
            "items": completed,
        },
        "in_progress": {
            "count": len(in_progress),
            "delta": len(in_progress) - int(previous.get("in_progress_count", 0)),
            "items": in_progress,
        },
        "pending": {
            "count": len(pending),
            "delta": len(pending) - int(previous.get("pending_count", 0)),
            "items": pending,
        },
        "important": {
            "count": len(important_items),
            "delta": len(important_items) - int(previous.get("important_count", 0)),
            "items": important_items,
        },
    }

    deadlines = {
        "overdue": overdue,
        "due_today": due_today,
        "due_next_3_days": due_next_3_days,
        "missing_due": missing_due,
        "stale_unupdated": stale_unupdated,
    }
    ai_summary = _build_ai_summary(
        completed,
        in_progress,
        pending,
        blocked,
        important_items,
        deadlines,
    )
    return {
        "metrics": metrics,
        "ai_summary": ai_summary,
        "changes": changes,
        "important_items": important_items,
        "timeline": timeline,
        "deadlines": deadlines,
        "github_activity": github_activity or {},
        "sync": sync or {},
        "snapshot": {
            "completed_count": len(completed),
            "in_progress_count": len(in_progress),
            "pending_count": len(pending),
            "important_count": len(important_items),
            "item_keys": sorted(current_keys),
            "pending_keys": sorted(current_pending),
            "completed_keys": sorted(current_completed),
            "stale_counts": stale_counts,
        },
    }


def _build_ai_summary(
    completed: list[dict[str, Any]],
    in_progress: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    important_items: list[dict[str, Any]],
    deadlines: dict[str, Any] | None = None,
) -> list[str]:
    completed_titles = [item["title"] for item in completed[:2]]
    summary: list[str] = []
    if completed_titles:
        summary.append(
            f"今日完成 {len(completed)} 项，主要包括：" + "、".join(completed_titles) + "。"
        )
    else:
        summary.append("今日暂无已完成的飞书任务或代码产出。")

    deadline_info = deadlines or {}
    overdue = deadline_info.get("overdue") or []
    due_next_3 = deadline_info.get("due_next_3_days") or []
    due_today = deadline_info.get("due_today") or []
    missing_due = deadline_info.get("missing_due") or []
    if overdue:
        summary.append(
            f"有 {len(overdue)} 项任务已经逾期，最紧急的是：{overdue[0]['title']}。"
        )
    elif due_today or due_next_3:
        not_started = [
            item
            for item in (due_today + due_next_3)
            if item.get("status") == "待处理"
        ]
        summary.append(
            f"发现 {len(due_today) + len(due_next_3)} 项任务将在 3 天内到期"
            + (f"，其中 {len(not_started)} 项尚未开始。" if not_started else "。")
        )
    if missing_due:
        summary.append(
            f"有 {len(missing_due)} 项重点任务缺少截止日期，建议补充明确完成时间。"
        )

    if in_progress or pending:
        summary.append(
            f"当前有 {len(in_progress)} 项工作正在推进，{len(pending)} 项待处理，"
            "建议优先明确下一项可交付结果。"
        )
    else:
        summary.append("当前没有进行中或待处理事项，项目状态较为稳定。")

    if blocked:
        summary.append("当前最需关注：" + "、".join(item["title"] for item in blocked[:2]) + "。")
    elif important_items:
        top_priority = important_items[0]
        summary.append(
            f"当前最需关注：{top_priority['title']}，优先级为{top_priority['priority']}。"
        )
    else:
        summary.append("当前未发现高优先级阻塞事项。")

    if pending:
        summary.append(f"明天优先处理：{pending[0]['title']}。")
    elif in_progress:
        summary.append(f"明天优先继续推进：{in_progress[0]['title']}。")
    else:
        summary.append("明天建议核实项目进展与版本交付情况。")
    return summary
