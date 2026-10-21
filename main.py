"""智能日报生成器。

网页模式：python main.py
命令行模式：python main.py --dry-run [--demo]
流程：GitHub / 飞书采集 → 聚合 → 生成 → 邮件与飞书推送
"""

from __future__ import annotations

import argparse
import html
import os
import secrets
import smtplib
import sys
import time as time_module
from dataclasses import asdict, is_dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, request
from flask_cors import CORS

from collector import github as github_collector
from collector import github_activity as github_activity_collector
from collector import lark_msg as lark_msg_collector
from collector import lark_task as lark_task_collector
from collector.github import CommitRecord
from collector.lark_msg import MessageRecord
from collector.lark_task import TaskRecord
from collector.result import CollectResult
from generator.formatter import DailyReport, MemberReport, build_report_subject, generate
from notifier import email as email_notifier
from notifier import lark_bot as lark_bot_notifier
from shared.config import (
    AppConfig,
    EmailNotifierConfig,
    GitHubConfig,
    LarkBotConfig,
    LarkConfig,
    MemberConfig,
    NotifierConfig,
    load_config,
)
from shared.errors import ConfigError
from shared.logger import get_logger
from shared.oauth import (
    OAuthError,
    add_app_to_tasklist,
    build_authorize_url,
    exchange_code,
)
from shared.storage import ReportStorage

logger = get_logger("main")

app = Flask(__name__)
CORS(app)
app.json.ensure_ascii = False


def _load_env_file(path: Path | None = None) -> None:
    """加载工作区 .env（已加入 .gitignore），环境变量优先。"""
    env_path = path or Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_env_file()

_OAUTH_STATES: dict[str, float] = {}
_OAUTH_STATE_TTL_SECONDS = 600


def _report_timezone() -> timezone:
    """返回日报日期使用的时区，默认北京时间 UTC+8。"""
    raw = os.getenv("REPORT_TZ_OFFSET", "8")
    try:
        offset_hours = float(raw)
    except ValueError:
        offset_hours = 8.0
    return timezone(timedelta(hours=offset_hours))


def _day_window(report_date: date) -> tuple[datetime, datetime]:
    """返回指定日报日期在本地时区对应的时间窗口。"""
    tz = _report_timezone()
    since = datetime.combine(report_date, time.min, tzinfo=tz)
    now = datetime.now(tz)
    if report_date == now.date():
        until = now
    else:
        until = datetime.combine(report_date, time.max, tzinfo=tz)
    return since, until


def _split_env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return list(default or [])
    items = raw.replace("，", ",").replace(";", ",").split(",")
    return [item.strip() for item in items if item.strip()]


def _filter_commits(records: list[CommitRecord], github_username: str) -> list[CommitRecord]:
    if not github_username:
        return []
    return [record for record in records if record.author.lower() == github_username.lower()]


def _filter_tasks(records: list[TaskRecord], lark_id: str) -> list[TaskRecord]:
    if not lark_id:
        return []
    needle = lark_id.lower()
    return [record for record in records if needle in record.assignee.lower()]


def _filter_messages(records: list[MessageRecord], lark_id: str) -> list[MessageRecord]:
    if not lark_id:
        return []
    needle = lark_id.lower()
    return [record for record in records if needle in record.sender.lower()]


def _safe_collect(name: str, fn: Any, *args: Any, **kwargs: Any) -> CollectResult:
    """单源异常不中断整体流程。"""
    try:
        result = fn(*args, **kwargs)
        if isinstance(result, CollectResult):
            return result
        return CollectResult(success=True, records=list(result))
    except Exception as exc:  # noqa: BLE001 — 编排层统一降级
        logger.error("数据源采集异常，已跳过", extra={"source": name, "error": str(exc)})
        return CollectResult(success=False, records=[], error_message=str(exc))


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _config_from_env(member_name: str | None = None) -> AppConfig:
    name = member_name or os.getenv("REPORT_MEMBER_NAME", "冯诗祺")
    member = MemberConfig(
        name=name,
        github=os.getenv("REPORT_MEMBER_GITHUB", os.getenv("GITHUB_USER", "")),
        lark=os.getenv("REPORT_MEMBER_LARK", os.getenv("LARK_MEMBER_ID", "")),
    )
    return AppConfig(
        team_name=os.getenv("REPORT_TEAM_NAME", "智能日报"),
        members=[member],
        github=GitHubConfig(repos=_split_env_list("GITHUB_REPOS")),
        lark=LarkConfig(
            project_id=os.getenv("LARK_PROJECT_ID", ""),
            chat_id=os.getenv("LARK_CHAT_ID", ""),
            keywords=_split_env_list(
                "LARK_KEYWORDS",
                ["进度", "阻塞", "评审", "完成", "会议"],
            ),
            app_id=os.getenv("LARK_APP_ID", ""),
            app_secret=os.getenv("LARK_APP_SECRET", ""),
        ),
        notifier=NotifierConfig(
            email=EmailNotifierConfig(recipients=_split_env_list("MAIL_RECIPIENTS")),
            lark_bot=LarkBotConfig(chat_id=os.getenv("LARK_NOTIFY_CHAT_ID", "")),
        ),
        raw={},
    )


def _select_member(config: AppConfig, member_name: str | None = None) -> MemberConfig:
    if member_name:
        for member in config.members:
            if member.name == member_name:
                return member
        return MemberConfig(
            name=member_name,
            github=os.getenv("REPORT_MEMBER_GITHUB", os.getenv("GITHUB_USER", "")),
            lark=os.getenv("REPORT_MEMBER_LARK", os.getenv("LARK_MEMBER_ID", "")),
        )
    if config.members:
        return config.members[0]
    raise ConfigError("配置中没有可用成员")


def load_runtime_config(
    member_name: str | None = None,
    config_path: str | Path | None = None,
) -> AppConfig:
    """加载网页请求使用的配置；无 config.yaml 时从环境变量构建。"""
    path = Path(config_path or os.getenv("REPORT_CONFIG_PATH", "config.yaml"))
    config = load_config(path) if path.exists() else _config_from_env(member_name)
    selected = _select_member(config, member_name)
    return replace(config, members=[selected])


def _source_warnings(config: AppConfig, member: MemberConfig) -> list[str]:
    warnings: list[str] = []
    lark_app_id = config.lark.app_id or os.getenv("LARK_APP_ID", "")
    lark_app_secret = config.lark.app_secret or os.getenv("LARK_APP_SECRET", "")
    if not lark_app_id or not lark_app_secret:
        warnings.append("未配置 LARK_APP_ID / LARK_APP_SECRET，飞书数据无法采集")
    if not config.lark.project_id and not config.lark.chat_id:
        warnings.append("未配置 LARK_PROJECT_ID / LARK_CHAT_ID，飞书任务和消息无法采集")
    if not member.lark:
        warnings.append("未配置 REPORT_MEMBER_LARK / LARK_MEMBER_ID，无法按成员匹配飞书数据")
    if not os.getenv("GITHUB_TOKEN"):
        warnings.append("未配置 GITHUB_TOKEN，GitHub 采集可能受接口限流")
    return warnings


def _github_activity_enabled() -> bool:
    return os.getenv("GITHUB_ACTIVITY_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _collect_sources(
    config: AppConfig,
    since: datetime,
    until: datetime,
    *,
    demo: bool = False,
) -> tuple[CollectResult[CommitRecord], CollectResult[TaskRecord], CollectResult[MessageRecord]]:
    if demo:
        return _demo_results(config, since)

    github_result = _safe_collect(
        "github",
        github_collector.collect,
        config.github.repos,
        since,
        until,
        max_retries=1,
        retry_interval=0,
        sleep_fn=lambda _: None,
    )
    task_result = _safe_collect(
        "lark_task",
        lark_task_collector.collect,
        config.lark.project_id,
        since,
        until,
        app_id=config.lark.app_id or None,
        app_secret=config.lark.app_secret or None,
        max_retries=1,
        retry_interval=0,
        sleep_fn=lambda _: None,
    )
    msg_result = _safe_collect(
        "lark_msg",
        lark_msg_collector.collect,
        config.lark.chat_id,
        config.lark.keywords,
        since,
        until,
        app_id=config.lark.app_id or None,
        app_secret=config.lark.app_secret or None,
        sender_names={member.lark: member.name for member in config.members if member.lark},
        resolve_chat_name=True,
        max_retries=1,
        retry_interval=0,
        sleep_fn=lambda _: None,
    )
    return github_result, task_result, msg_result


def _build_report(
    config: AppConfig,
    report_date: date,
    *,
    member_name: str | None = None,
    demo: bool = False,
) -> tuple[DailyReport | None, dict[str, Any]]:
    """采集并生成日报，返回日报对象与供前端展示的结构化原始数据。"""
    since, until = _day_window(report_date)
    github_result, task_result, msg_result = _collect_sources(
        config,
        since,
        until,
        demo=demo,
    )

    logger.info(
        "各数据源采集条数",
        extra={
            "github_count": len(github_result.records),
            "github_success": github_result.success,
            "lark_task_count": len(task_result.records),
            "lark_task_success": task_result.success,
            "lark_msg_count": len(msg_result.records),
            "lark_msg_success": msg_result.success,
        },
    )

    github_activity_data: dict[str, Any] = {}
    github_activity_status = {"success": True, "error": None}
    if _github_activity_enabled() and config.github.repos:
        activity_member = _select_member(config, member_name)
        try:
            github_activity_data = github_activity_collector.collect_activity(
                config.github.repos,
                since,
                until,
                activity_member.github,
            )
            github_activity_status = {
                "success": bool(github_activity_data.get("success")),
                "error": github_activity_data.get("error"),
            }
            github_activity_data.setdefault("counts", {})["commits"] = len(github_result.records)
        except Exception as exc:  # noqa: BLE001
            github_activity_status = {"success": False, "error": str(exc)}

    sources = {
        "github": {"success": github_result.success, "error": github_result.error_message},
        "github_activity": github_activity_status,
        "lark_task": {"success": task_result.success, "error": task_result.error_message},
        "lark_msg": {"success": msg_result.success, "error": msg_result.error_message},
    }

    if not github_result.success and not task_result.success and not msg_result.success:
        logger.error("所有数据源采集失败，不生成空日报")
        return None, {
            "date": report_date.isoformat(),
            "member": member_name or (config.members[0].name if config.members else ""),
            "team_name": config.team_name,
            "github": [],
            "lark_task": [],
            "lark_msg": [],
            "sources": sources,
            "warnings": _source_warnings(config, config.members[0]) if config.members else [],
        }

    target_members = [_select_member(config, member_name)] if member_name else config.members
    member_reports: list[MemberReport] = []
    member_raw: list[dict[str, Any]] = []
    warnings: list[str] = []

    for member in target_members:
        commits = (
            None
            if not github_result.success
            else _filter_commits(github_result.records, member.github)
        )
        tasks = (
            None
            if not task_result.success
            else _filter_tasks(task_result.records, member.lark)
        )
        messages = (
            None
            if not msg_result.success
            else _filter_messages(msg_result.records, member.lark)
        )
        member_reports.append(
            MemberReport(
                name=member.name,
                github_username=member.github,
                commits=commits,
                tasks=tasks,
                messages=messages,
            )
        )
        member_raw.append(
            {
                "name": member.name,
                "github": _jsonable(commits or []),
                "lark_task": _jsonable(tasks or []),
                "lark_msg": _jsonable(messages or []),
            }
        )
        warnings.extend(_source_warnings(config, member))

    previous_snapshot = None
    trend: list[dict] = []
    try:
        storage = ReportStorage()
        previous_record = storage.get_report(
            report_date - timedelta(days=1),
            config.team_name,
        )
        if previous_record and previous_record.insights:
            previous_snapshot = previous_record.insights.get("snapshot")
        recent_records = storage.list_reports(limit=7)
        trend = [
            {
                "date": record.report_date.isoformat(),
                "completed": int(
                    (record.insights.get("metrics", {}).get("completed", {}) or {}).get("count", 0)
                ),
                "in_progress": int(
                    (record.insights.get("metrics", {}).get("in_progress", {}) or {}).get("count", 0)
                ),
                "pending": int(
                    (record.insights.get("metrics", {}).get("pending", {}) or {}).get("count", 0)
                ),
            }
            for record in reversed(recent_records)
        ]
    except Exception as exc:  # noqa: BLE001
        logger.info("历史洞察读取失败，跳过趋势对比", extra={"error": str(exc)})

    sync_info = {
        "last_synced": datetime.now(_report_timezone()).isoformat(),
        "time_range": f"{since.isoformat()} ~ {until.isoformat()}",
        "source_status": sources,
    }
    report = generate(
        member_reports,
        report_date,
        config.team_name,
        previous_snapshot=previous_snapshot,
        trend=trend,
        sync=sync_info,
        github_activity=github_activity_data,
    )
    logger.info(
        "日报生成完成",
        extra={"markdown_length": len(report.markdown), "html_length": len(report.html)},
    )

    raw_info = {
        "date": report_date.isoformat(),
        "member": target_members[0].name if len(target_members) == 1 else "",
        "team_name": config.team_name,
        "members": member_raw,
        "github": _jsonable(github_result.records) if github_result.success else [],
        "lark_task": _jsonable(task_result.records) if task_result.success else [],
        "lark_msg": _jsonable(msg_result.records) if msg_result.success else [],
        "sources": sources,
        "warnings": list(dict.fromkeys(warnings)),
        "insights": report.insights,
        "github_activity": github_activity_data,
    }
    return report, raw_info


def _save_report(report: DailyReport) -> None:
    try:
        storage = ReportStorage()
        storage.save_report(
            report_date=report.date,
            team_name=report.team_name,
            markdown=report.markdown,
            html=report.html,
            generated_at=report.generated_at,
            insights=report.insights,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("日报落库失败", extra={"error": str(exc)})


def _schedule_recipients(config: AppConfig) -> list[str]:
    recipients = _split_env_list("REPORT_SCHEDULE_TO")
    if recipients:
        return recipients
    return list(config.notifier.email.recipients)


def _run_scheduled_report() -> int:
    """生成当天日报并发送给定时收件人；供云端定时任务调用。"""
    try:
        config = load_runtime_config()
    except ConfigError as exc:
        logger.error("定时日报配置加载失败", extra={"error": str(exc)})
        return 1

    recipients = _schedule_recipients(config)
    if not recipients:
        logger.error("定时日报未配置收件人")
        return 1

    report_date = _default_report_date()
    report, _ = _build_report(
        config,
        report_date,
        member_name=config.members[0].name if config.members else None,
    )
    if report is None:
        logger.error("定时日报生成失败：所有数据源不可用")
        return 1

    failed: list[str] = []
    for recipient in recipients:
        try:
            _send_report_email(report, recipient)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{recipient}: {exc}")

    _save_report(report)
    logger.info(
        "定时日报发送完成",
        extra={"recipients": recipients, "failed": failed, "date": report_date.isoformat()},
    )
    return 0 if not failed else 1


def _send_report_email(report: DailyReport, recipient: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.qq.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("MAIL_USER") or os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("MAIL_AUTH_CODE") or os.getenv("SMTP_PASSWORD", "")
    use_ssl = os.getenv("SMTP_USE_SSL", "true").lower() not in {"0", "false", "no"}

    if not smtp_user or not smtp_password:
        raise RuntimeError("尚未配置发件邮箱或邮箱授权码")

    message = EmailMessage()
    message["Subject"] = build_report_subject(report)
    message["From"] = smtp_user
    message["To"] = recipient
    message.set_content(report.markdown)
    message.add_alternative(report.html, subtype="html")

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as smtp:
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def _demo_results(
    config: AppConfig,
    since: datetime,
) -> tuple[
    CollectResult[CommitRecord],
    CollectResult[TaskRecord],
    CollectResult[MessageRecord],
]:
    """本地演示数据：不依赖外部 API。"""
    member = config.members[0]
    commits = CollectResult(
        success=True,
        records=[
            CommitRecord(
                author=member.github,
                message="feat: demo commit",
                timestamp=since,
                repo=config.github.repos[0] if config.github.repos else "demo/repo",
                additions=8,
                deletions=1,
                files_changed=1,
            )
        ],
    )
    tasks = CollectResult(
        success=True,
        records=[
            TaskRecord(
                assignee=member.lark,
                title="演示任务",
                status_from="todo",
                status_to="done",
                updated_at=since,
            )
        ],
    )
    messages = CollectResult(
        success=True,
        records=[
            MessageRecord(
                sender=member.lark,
                content="进度同步：演示消息",
                timestamp=since,
                chat_name="演示群",
            )
        ],
    )
    return commits, tasks, messages


def run_pipeline(config: AppConfig, *, dry_run: bool = False, demo: bool = False) -> int:
    started_at = datetime.now(timezone.utc)
    report_date = datetime.now(_report_timezone()).date()

    logger.info(
        "日报流程开始",
        extra={
            "start_time": started_at.isoformat(),
            "team_name": config.team_name,
            "date": report_date.isoformat(),
            "dry_run": dry_run,
            "demo": demo,
        },
    )

    report, _ = _build_report(config, report_date, demo=demo)
    if report is None:
        ended_at = datetime.now(timezone.utc)
        logger.info(
            "日报流程结束",
            extra={"end_time": ended_at.isoformat(), "generated": False},
        )
        return 1

    _save_report(report)

    email_ok = False
    lark_ok = False
    if dry_run:
        logger.info("dry-run 模式：跳过推送")
    else:
        email_ok = email_notifier.send(report, config.notifier.email.recipients)
        lark_ok = lark_bot_notifier.send(report, config.notifier.lark_bot.chat_id)
        logger.info("推送结果", extra={"email": email_ok, "lark_bot": lark_ok})

    ended_at = datetime.now(timezone.utc)
    logger.info(
        "日报流程结束",
        extra={
            "end_time": ended_at.isoformat(),
            "start_time": started_at.isoformat(),
            "generated": True,
            "dry_run": dry_run,
            "email": email_ok if not dry_run else None,
            "lark_bot": lark_ok if not dry_run else None,
        },
    )
    return 0


def run_check(config: AppConfig) -> int:
    """验证配置与关键环境变量 / 连接前置条件。"""
    ok = True
    logger.info("开始健康检查")

    checks = [
        ("GITHUB_TOKEN", bool(os.getenv("GITHUB_TOKEN"))),
        (
            "LARK_APP_ID",
            bool(config.lark.app_id or os.getenv("LARK_APP_ID")),
        ),
        (
            "LARK_APP_SECRET",
            bool(config.lark.app_secret or os.getenv("LARK_APP_SECRET")),
        ),
        ("SMTP_HOST", bool(os.getenv("SMTP_HOST"))),
        ("LARK_BOT_WEBHOOK", bool(os.getenv("LARK_BOT_WEBHOOK"))),
        ("github.repos", bool(config.github.repos)),
        ("lark.project_id", bool(config.lark.project_id)),
        ("lark.chat_id", bool(config.lark.chat_id)),
        ("notifier.email.recipients", bool(config.notifier.email.recipients)),
        ("notifier.lark_bot.chat_id", bool(config.notifier.lark_bot.chat_id)),
        ("members", bool(config.members)),
    ]
    for name, passed in checks:
        if passed:
            logger.info("检查通过", extra={"check": name})
        else:
            ok = False
            logger.error("检查失败", extra={"check": name})

    logger.info("健康检查结束", extra={"ok": ok})
    return 0 if ok else 1


def _parse_report_date(raw_value: Any) -> date:
    if isinstance(raw_value, date):
        return raw_value
    if raw_value is None or not str(raw_value).strip():
        return _default_report_date()
    try:
        return date.fromisoformat(str(raw_value).strip())
    except ValueError as exc:
        raise ValueError("日期格式必须为 YYYY-MM-DD") from exc


def _default_report_date() -> date:
    """默认日报日期，可通过 REPORT_DATE_OFFSET 调整为昨天等。"""
    try:
        offset = int(os.getenv("REPORT_DATE_OFFSET", "0"))
    except ValueError:
        offset = 0
    return datetime.now(_report_timezone()).date() + timedelta(days=offset)


def _oauth_redirect_uri() -> str:
    return os.getenv(
        "FEISHU_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:5000/oauth/callback",
    )


def _oauth_scopes() -> list[str]:
    return [
        "offline_access",
        "task:tasklist:read",
        "task:tasklist:write",
        "task:task:read",
    ]


def _oauth_marker_path() -> Path:
    return Path(__file__).with_name("data") / "oauth_authorization.json"


def _write_oauth_marker(config: AppConfig) -> None:
    marker = _oauth_marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        (
            "{\n"
            f'  "app_id": "{config.lark.app_id}",\n'
            f'  "tasklist_guid": "{config.lark.project_id}",\n'
            f'  "authorized_at": "{datetime.now(timezone.utc).isoformat()}"\n'
            "}\n"
        ),
        encoding="utf-8",
    )


@app.get("/api/oauth/status")
def api_oauth_status():
    config = load_runtime_config()
    marker = _oauth_marker_path()
    return jsonify(
        {
            "code": 0,
            "authorized": marker.exists(),
            "redirect_uri": _oauth_redirect_uri(),
            "tasklist_guid": config.lark.project_id,
            "scopes": _oauth_scopes(),
        }
    )


@app.get("/api/oauth/start")
def api_oauth_start():
    try:
        config = load_runtime_config()
    except ConfigError as exc:
        return jsonify({"code": 1, "message": str(exc)}), 400

    if not config.lark.app_id or not config.lark.app_secret:
        return jsonify({"code": 1, "message": "未配置飞书 App ID / App Secret"}), 500
    if not config.lark.project_id:
        return jsonify({"code": 1, "message": "未配置飞书任务清单 ID"}), 400

    now = time_module.time()
    for state_value, created_at in list(_OAUTH_STATES.items()):
        if now - created_at > _OAUTH_STATE_TTL_SECONDS:
            _OAUTH_STATES.pop(state_value, None)

    state = secrets.token_urlsafe(32)
    _OAUTH_STATES[state] = now
    authorize_url = build_authorize_url(
        app_id=config.lark.app_id,
        redirect_uri=_oauth_redirect_uri(),
        state=state,
        scopes=_oauth_scopes(),
    )
    return redirect(authorize_url)


@app.get("/oauth/callback")
def oauth_callback():
    state = request.args.get("state", "")
    created_at = _OAUTH_STATES.get(state)
    if not state or created_at is None or time_module.time() - created_at > _OAUTH_STATE_TTL_SECONDS:
        return "<h1>授权失败</h1><p>state 无效或已过期，请重新发起授权。</p>", 400

    if request.args.get("error"):
        error = html.escape(request.args.get("error", "access_denied"))
        return f"<h1>授权已取消</h1><p>{error}</p>", 400

    code = request.args.get("code", "")
    if not code:
        return "<h1>授权失败</h1><p>回调中缺少授权码。</p>", 400

    try:
        config = load_runtime_config()
        token_data = exchange_code(
            app_id=config.lark.app_id,
            app_secret=config.lark.app_secret,
            code=code,
            redirect_uri=_oauth_redirect_uri(),
        )
        add_app_to_tasklist(
            user_access_token=str(token_data["access_token"]),
            tasklist_guid=config.lark.project_id,
            app_id=config.lark.app_id,
        )
        _write_oauth_marker(config)
        _OAUTH_STATES.pop(state, None)
    except (ConfigError, OAuthError, KeyError) as exc:
        app.logger.exception("飞书任务清单 OAuth 授权失败")
        message = html.escape(str(exc))
        return f"<h1>任务清单授权失败</h1><p>{message}</p>", 500
    except Exception:
        app.logger.exception("飞书任务清单 OAuth 授权异常")
        return "<h1>任务清单授权失败</h1><p>请查看服务器日志。</p>", 500

    return (
        "<h1>任务清单授权成功</h1>"
        "<p>应用已加入任务清单协作者，可以关闭此页面并返回系统。</p>"
    )


@app.post("/api/report")
def api_report():
    req_data = request.get_json(silent=True) or {}
    try:
        report_date = _parse_report_date(req_data.get("date"))
        member_name = str(req_data.get("member") or "").strip() or None
        config = load_runtime_config(member_name)
        report, raw_info = _build_report(
            config,
            report_date,
            member_name=member_name,
        )
    except (ConfigError, ValueError) as exc:
        return jsonify({"code": 1, "message": str(exc)}), 400
    except Exception:
        app.logger.exception("日报生成失败")
        return jsonify({"code": 1, "message": "系统生成日报失败，请检查服务器日志"}), 500

    if report is None:
        return jsonify({
            "code": 1,
            "message": "所有数据源采集失败，暂时无法生成日报",
            "raw": raw_info,
        }), 502

    _save_report(report)
    return jsonify({
        "code": 0,
        "raw": raw_info,
        "data": report.markdown,
        "html": report.html,
        "insights": report.insights,
        "meta": {
            "team_name": report.team_name,
            "member": raw_info.get("member"),
            "date": report.date.isoformat(),
            "generated_at": report.generated_at.isoformat(),
            "warnings": raw_info.get("warnings", []),
        },
    })


@app.post("/api/send-report")
def api_send_report():
    req_data = request.get_json(silent=True) or {}
    to_email = str(req_data.get("to_email") or "").strip()
    member_name = str(req_data.get("member") or "").strip() or None

    try:
        report_date = _parse_report_date(req_data.get("date"))
        config = load_runtime_config(member_name)
        recipient = to_email or (
            config.notifier.email.recipients[0] if config.notifier.email.recipients else ""
        )
        if not recipient:
            return jsonify({"code": 1, "message": "请填写老师邮箱"}), 400

        report, raw_info = _build_report(
            config,
            report_date,
            member_name=member_name,
        )
    except (ConfigError, ValueError) as exc:
        return jsonify({"code": 1, "message": str(exc)}), 400
    except Exception:
        app.logger.exception("日报自动生成失败")
        return jsonify({"code": 1, "message": "系统生成日报失败，请检查服务器日志"}), 500

    if report is None:
        return jsonify({
            "code": 1,
            "message": "飞书及其他数据源均采集失败，邮件未发送",
            "raw": raw_info,
        }), 502

    try:
        _send_report_email(report, recipient)
    except RuntimeError as exc:
        return jsonify({"code": 1, "message": str(exc)}), 500
    except Exception:
        app.logger.exception("日报邮件发送失败")
        return jsonify({
            "code": 1,
            "message": "邮件发送失败，请检查邮箱配置和服务器日志"
        }), 500

    _save_report(report)
    return jsonify({
        "code": 0,
        "message": "日报已由系统自动生成并提交发送",
        "data": report.markdown,
        "html": report.html,
        "insights": report.insights,
        "raw": raw_info,
        "meta": {
            "recipient": recipient,
            "date": report.date.isoformat(),
            "warnings": raw_info.get("warnings", []),
        },
    })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智能日报生成器")
    parser.add_argument("--check", action="store_true", help="验证配置与 API 连接前置条件")
    parser.add_argument("--dry-run", action="store_true", help="执行采集和生成，但不推送")
    parser.add_argument("--demo", action="store_true", help="使用本地 mock 数据跑通流程")
    parser.add_argument("--send-now", action="store_true", help="立即生成并发送当天日报")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径（默认 config.yaml）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config)
    if not config_path.exists():
        example = Path("config.yaml.example")
        if example.exists():
            logger.info("未找到 config.yaml，回退使用 config.yaml.example")
            config_path = example
        else:
            logger.error("配置文件不存在", extra={"path": str(config_path)})
            return 1

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        logger.error("配置加载失败", extra={"error": str(exc)})
        return 1

    if args.check:
        return run_check(config)
    if args.send_now:
        return _run_scheduled_report()
    return run_pipeline(config, dry_run=args.dry_run, demo=args.demo)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(main())
    app.run(host="127.0.0.1", port=5000, debug=True)
