"""日报 Markdown / HTML 模板与格式转换。"""

from __future__ import annotations

import html
import re

from jinja2 import Template

MARKDOWN_TEMPLATE = Template(
    """# {{ team_name }} 日报 {{ date }}

{% if insights and insights.ai_summary %}
## AI 今日总结

{% for line in insights.ai_summary -%}
- {{ line }}
{% endfor %}
{% endif %}

{% if insights and insights.metrics %}
## 今日概览

- 今日完成任务数：{{ insights.metrics.completed.count }}（较昨日变化 {{ insights.metrics.completed.delta }}）
- 进行中任务数：{{ insights.metrics.in_progress.count }}（较昨日变化 {{ insights.metrics.in_progress.delta }}）
- 待处理任务数：{{ insights.metrics.pending.count }}（较昨日变化 {{ insights.metrics.pending.delta }}）
- 今日重要事项数：{{ insights.metrics.important.count }}（较昨日变化 {{ insights.metrics.important.delta }}）
{% endif %}

{% if insights and insights.changes %}
## 每日变化对比

- 新增事项：{% if insights.changes.added %}{% for item in insights.changes.added %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 已完成事项：{% if insights.changes.completed %}{% for item in insights.changes.completed %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 进行中事项：{% if insights.changes.in_progress %}{% for item in insights.changes.in_progress %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 阻塞事项：{% if insights.changes.blocked %}{% for item in insights.changes.blocked %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 持续无变化事项：{% if insights.changes.stale %}{% for item in insights.changes.stale %}{{ item.title }}（连续 {{ item.days }} 天）{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
{% endif %}

{% if insights and insights.deadlines %}
## 截止日期与风险预警

- 已逾期：{% if insights.deadlines.overdue %}{% for item in insights.deadlines.overdue %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 今日到期：{% if insights.deadlines.due_today %}{% for item in insights.deadlines.due_today %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 未来 3 天到期：{% if insights.deadlines.due_next_3_days %}{% for item in insights.deadlines.due_next_3_days %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 长期未更新：{% if insights.deadlines.stale_unupdated %}{% for item in insights.deadlines.stale_unupdated %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
- 缺少截止日期：{% if insights.deadlines.missing_due %}{% for item in insights.deadlines.missing_due %}{{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}{% else %}无{% endif %}
{% endif %}

{% for member in members %}
## {{ member.name }}

{% if member.is_empty %}
*今日无记录*
{% else %}
### 代码提交
{% if member.commits_failed %}
- 数据获取失败
{% elif member.commits %}
{% for c in member.commits -%}
- `{{ c.repo }}` {{ c.message }} (+{{ c.additions }}/-{{ c.deletions }}, {{ c.files_changed }} files)
{% endfor %}
{% else %}
- 无
{% endif %}

### 任务进展
{% if member.tasks_failed %}
- 数据获取失败
{% elif member.tasks %}
{% for t in member.tasks -%}
- {{ t.title }}（{{ t.status_from }} → {{ t.status_to }}）
{% endfor %}
{% else %}
- 无
{% endif %}

### 协作沟通
{% if member.messages_failed %}
- 数据获取失败
{% elif member.messages %}
{% for m in member.messages -%}
- {{ m.sender_name or m.chat_name }}：{{ m.content }}
{% endfor %}
{% else %}
- 无
{% endif %}
{% endif %}

{% endfor %}

{% if insights and insights.important_items %}
## 重点事项与下一步

{% for item in insights.important_items -%}
- [{{ item.priority }}优先级] {{ item.title }}｜状态：{{ item.status }}｜来源：{{ item.source }}{% if item.due %}｜截止：{{ item.due }}{% endif %}{% if item.next_action %}｜下一步：{{ item.next_action }}{% endif %}
{% endfor %}
{% endif %}

{% if insights and insights.timeline %}
## 工作产出与项目进展

{% for item in insights.timeline[:20] -%}
- [{{ item.source }}] {{ item.title }}｜状态：{{ item.status }}｜优先级：{{ item.priority }}{% if item.owner %}｜负责人：{{ item.owner }}{% endif %}
{% endfor %}
{% endif %}

{% if insights and insights.github_activity %}
## GitHub 科研代码追踪

- 提交：{{ insights.github_activity.counts.commits or 0 }}
- Pull Request：{{ insights.github_activity.counts.pull_requests or 0 }}
- Issue：{{ insights.github_activity.counts.issues or 0 }}
- 代码评审：{{ insights.github_activity.counts.reviews or 0 }}
{% if insights.github_activity.pull_requests %}
- PR 明细：{% for item in insights.github_activity.pull_requests %}#{{ item.number }} {{ item.title }}（{{ item.state }}）{% if not loop.last %}；{% endif %}{% endfor %}
{% endif %}
{% if insights.github_activity.issues %}
- Issue 明细：{% for item in insights.github_activity.issues %}#{{ item.number }} {{ item.title }}（{{ item.state }}）{% if not loop.last %}；{% endif %}{% endfor %}
{% endif %}
{% if insights.github_activity.reviews %}
- 评审明细：{% for item in insights.github_activity.reviews %}#{{ item.number }} {{ item.title }}{% if not loop.last %}；{% endif %}{% endfor %}
{% endif %}
{% if insights.metrics.completed.count > 0 and (insights.github_activity.counts.commits or 0) == 0 %}
- 说明：本期没有 GitHub 提交，但飞书任务有完成记录，不能直接判断科研活动停滞。
{% endif %}
{% endif %}

{% if insights and insights.sync %}
## 数据同步状态

- 最后同步时间：{{ insights.sync.last_synced or "未知" }}
- 统计时间范围：{{ insights.sync.time_range or "未知" }}
{% if insights.sync.source_status %}
- 数据源状态：{% for name, state in insights.sync.source_status.items() %}{{ name }}={{ "成功" if state.success else "失败" }}{% if not loop.last %}；{% endif %}{% endfor %}
{% endif %}
{% endif %}
""".strip()
)


def render_markdown(*, team_name: str, date: str, members: list[dict], insights: dict | None = None) -> str:
    """使用 Jinja2 模板渲染 Markdown 日报。"""
    return MARKDOWN_TEMPLATE.render(
        team_name=team_name,
        date=date,
        members=members,
        insights=insights or {},
    ).strip() + "\n"


def markdown_to_html(markdown: str) -> str:
    """将日报 Markdown 转为可在浏览器渲染的简易 HTML。"""
    lines = markdown.splitlines()
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>日报</title>",
        "<style>",
        'body{font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.7;color:#222;padding:24px;}',
        "h1{color:#1b5e20;}",
        "h2{margin-top:24px;color:#2e7d32;border-bottom:1px solid #c8e6c9;padding-bottom:4px;}",
        "h3{color:#246f46;}",
        "code{background:#edf8f0;color:#1b5736;padding:1px 4px;border-radius:4px;}",
        "ul{padding-left:20px;}",
        "</style>",
        "</head>",
        "<body>",
    ]

    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            parts.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.rstrip()
        if not line:
            close_list()
            continue

        if line.startswith("# "):
            close_list()
            parts.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            close_list()
            parts.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            close_list()
            parts.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_inline_md(line[2:].strip())}</li>")
        elif line.startswith("*") and line.endswith("*") and len(line) > 2:
            close_list()
            parts.append(f"<p><em>{html.escape(line.strip('*').strip())}</em></p>")
        else:
            close_list()
            parts.append(f"<p>{_inline_md(line)}</p>")

    close_list()
    parts.extend(["</body>", "</html>"])
    return "\n".join(parts) + "\n"


def _inline_md(text: str) -> str:
    """处理行内 `code`，其余转义。"""
    parts: list[str] = []
    last = 0
    for match in re.finditer(r"`([^`]+)`", text):
        parts.append(html.escape(text[last:match.start()]))
        parts.append(f"<code>{html.escape(match.group(1))}</code>")
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)
