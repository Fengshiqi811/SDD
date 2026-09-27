"""日报 Markdown / HTML 模板与格式转换。"""

from __future__ import annotations

import html
import re

from jinja2 import Template

MARKDOWN_TEMPLATE = Template(
    """# {{ team_name }} 日报 {{ date }}

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
- [{{ m.chat_name }}] {{ m.content }}
{% endfor %}
{% else %}
- 无
{% endif %}
{% endif %}

{% endfor %}
""".strip()
)


def render_markdown(*, team_name: str, date: str, members: list[dict]) -> str:
    """使用 Jinja2 模板渲染 Markdown 日报。"""
    return MARKDOWN_TEMPLATE.render(team_name=team_name, date=date, members=members).strip() + "\n"


def markdown_to_html(markdown: str) -> str:
    """将日报 Markdown 转为可在浏览器渲染的简易 HTML。"""
    lines = markdown.splitlines()
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>日报</title>",
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
