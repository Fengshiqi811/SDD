"""智能日报生成器 — 主编排入口。

流程：采集 → 聚合 → 生成 → 推送
支持：--check（健康检查）、--dry-run（只采集生成不推送）
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

from collector import github as github_collector
from collector import lark_msg as lark_msg_collector
from collector import lark_task as lark_task_collector
from collector.github import CommitRecord
from collector.lark_msg import MessageRecord
from collector.lark_task import TaskRecord
from collector.result import CollectResult
from generator.formatter import MemberReport, generate
from notifier import email as email_notifier
from notifier import lark_bot as lark_bot_notifier
from shared.config import AppConfig, load_config
from shared.errors import ConfigError
from shared.logger import get_logger
from shared.storage import ReportStorage

logger = get_logger("main")


def _day_window(report_date: date) -> tuple[datetime, datetime]:
    since = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
    until = datetime.now(timezone.utc)
    if until.date() > report_date:
        until = datetime.combine(report_date, time.max, tzinfo=timezone.utc)
    return since, until


def _filter_commits(records: list[CommitRecord], github_username: str) -> list[CommitRecord]:
    return [r for r in records if r.author.lower() == github_username.lower()]


def _filter_tasks(records: list[TaskRecord], lark_id: str) -> list[TaskRecord]:
    needle = lark_id.lower()
    return [r for r in records if needle in r.assignee.lower()]


def _filter_messages(records: list[MessageRecord], lark_id: str) -> list[MessageRecord]:
    needle = lark_id.lower()
    return [r for r in records if needle in r.sender.lower()]


def _safe_collect(name: str, fn, *args, **kwargs) -> CollectResult:
    """单源异常不中断整体流程。"""
    try:
        result = fn(*args, **kwargs)
        if isinstance(result, CollectResult):
            return result
        return CollectResult(success=True, records=list(result))
    except Exception as exc:  # noqa: BLE001 — 编排层优雅降级
        logger.error("数据源采集异常，已跳过", extra={"source": name, "error": str(exc)})
        return CollectResult(success=False, records=[], error_message=str(exc))


def run_check(config: AppConfig) -> int:
    """验证配置与关键环境变量 / 连接前置条件。"""
    ok = True
    logger.info("开始健康检查")

    checks = [
        ("GITHUB_TOKEN", bool(os.getenv("GITHUB_TOKEN"))),
        ("LARK_APP_ID", bool(os.getenv("LARK_APP_ID"))),
        ("LARK_APP_SECRET", bool(os.getenv("LARK_APP_SECRET"))),
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

    # 轻量连通性探测（失败不抛，只记结果）
    try:
        import httpx

        with httpx.Client(timeout=5.0) as client:
            gh = client.get("https://api.github.com", headers={"User-Agent": "daily-report-check"})
            logger.info("GitHub API 可达", extra={"status": gh.status_code})
    except Exception as exc:  # noqa: BLE001
        ok = False
        logger.error("GitHub API 不可达", extra={"error": str(exc)})

    logger.info("健康检查结束", extra={"ok": ok})
    return 0 if ok else 1


def _demo_results(config: AppConfig, since: datetime) -> tuple[
    CollectResult[CommitRecord],
    CollectResult[TaskRecord],
    CollectResult[MessageRecord],
]:
    """本地演示数据：不依赖外部 API，用于验证聚合/生成/推送编排。"""
    member = config.members[0]
    commits = CollectResult(
        success=True,
        records=[
            CommitRecord(
                author=member.github,
                message="feat: demo commit",
                timestamp=since,
                repo=config.github.repos[0],
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
    report_date = started_at.date()
    since, until = _day_window(report_date)

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

    if demo:
        logger.info("demo 模式：使用本地 mock 采集数据")
        github_result, task_result, msg_result = _demo_results(config, since)
    else:
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
            max_retries=1,
            retry_interval=0,
            sleep_fn=lambda _: None,
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

    if not github_result.success and not task_result.success and not msg_result.success:
        logger.error("所有数据源采集失败，不生成空日报")
        ended_at = datetime.now(timezone.utc)
        logger.info(
            "日报流程结束",
            extra={"end_time": ended_at.isoformat(), "generated": False},
        )
        return 1

    members: list[MemberReport] = []
    for member in config.members:
        members.append(
            MemberReport(
                name=member.name,
                github_username=member.github,
                commits=(
                    None
                    if not github_result.success
                    else _filter_commits(github_result.records, member.github)
                ),
                tasks=(
                    None
                    if not task_result.success
                    else _filter_tasks(task_result.records, member.lark)
                ),
                messages=(
                    None
                    if not msg_result.success
                    else _filter_messages(msg_result.records, member.lark)
                ),
            )
        )

    report = generate(members, report_date, config.team_name)
    logger.info(
        "日报生成完成",
        extra={"markdown_length": len(report.markdown), "html_length": len(report.html)},
    )

    try:
        storage = ReportStorage()
        storage.save_report(
            report_date=report.date,
            team_name=report.team_name,
            markdown=report.markdown,
            html=report.html,
            generated_at=report.generated_at,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("日报落库失败", extra={"error": str(exc)})

    email_ok = False
    lark_ok = False
    if dry_run:
        logger.info("dry-run 模式：跳过推送")
    else:
        email_ok = email_notifier.send(report, config.notifier.email.recipients)
        lark_ok = lark_bot_notifier.send(report, config.notifier.lark_bot.chat_id)
        logger.info(
            "推送结果",
            extra={"email": email_ok, "lark_bot": lark_ok},
        )

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智能日报生成器")
    parser.add_argument(
        "--check",
        action="store_true",
        help="验证配置与 API 连接前置条件",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="执行采集和生成，但不推送",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用本地 mock 数据跑通聚合/生成流程（无需外部 API）",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="配置文件路径（默认 config.yaml）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

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
    return run_pipeline(config, dry_run=args.dry_run, demo=args.demo)


if __name__ == "__main__":
    sys.exit(main())
