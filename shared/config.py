"""读取并校验 config.yaml。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from shared.errors import ConfigError

REQUIRED_MEMBER_FIELDS = ("name", "github", "lark")


@dataclass(frozen=True)
class MemberConfig:
    name: str
    github: str
    lark: str


@dataclass(frozen=True)
class GitHubConfig:
    repos: list[str]


@dataclass(frozen=True)
class LarkConfig:
    project_id: str
    chat_id: str
    keywords: list[str]
    app_id: str = ""
    app_secret: str = ""


@dataclass(frozen=True)
class EmailNotifierConfig:
    recipients: list[str]


@dataclass(frozen=True)
class LarkBotConfig:
    chat_id: str


@dataclass(frozen=True)
class NotifierConfig:
    email: EmailNotifierConfig
    lark_bot: LarkBotConfig


@dataclass(frozen=True)
class AppConfig:
    team_name: str
    members: list[MemberConfig]
    github: GitHubConfig
    lark: LarkConfig
    notifier: NotifierConfig
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


def _require(data: dict[str, Any], key: str, path: str) -> Any:
    if key not in data or data[key] is None:
        raise ConfigError(f"配置缺少必填字段: {path}.{key}" if path else f"配置缺少必填字段: {key}")
    return data[key]


def _require_non_empty_str(value: Any, field_path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"配置字段无效（需为非空字符串）: {field_path}")
    return value


def _optional_non_empty_str(value: Any, field_path: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ConfigError(f"配置字段无效（需为字符串）: {field_path}")
    return value.strip()


def _require_list(value: Any, field_path: str) -> list[Any]:
    if not isinstance(value, list) or len(value) == 0:
        raise ConfigError(f"配置字段无效（需为非空列表）: {field_path}")
    return value


def _optional_list(value: Any, field_path: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"配置字段无效（需为列表）: {field_path}")
    return value


def _parse_members(raw_members: Any) -> list[MemberConfig]:
    members_data = _require_list(raw_members, "members")
    members: list[MemberConfig] = []
    for index, item in enumerate(members_data):
        if not isinstance(item, dict):
            raise ConfigError(f"配置字段无效: members[{index}] 应为对象")
        values: dict[str, str] = {}
        for key in REQUIRED_MEMBER_FIELDS:
            if key not in item or item[key] is None:
                raise ConfigError(f"配置缺少必填字段: members[{index}].{key}")
            values[key] = _require_non_empty_str(item[key], f"members[{index}].{key}")
        members.append(MemberConfig(**values))
    return members


def validate_config(data: dict[str, Any]) -> AppConfig:
    """校验原始配置字典并返回 AppConfig。"""
    if not isinstance(data, dict):
        raise ConfigError("配置根节点必须为对象")

    team_name = _require_non_empty_str(_require(data, "team_name", ""), "team_name")
    members = _parse_members(_require(data, "members", ""))

    github_raw = _require(data, "github", "")
    if not isinstance(github_raw, dict):
        raise ConfigError("配置字段无效: github 应为对象")
    repos = _optional_list(github_raw.get("repos"), "github.repos")
    for i, repo in enumerate(repos):
        _require_non_empty_str(repo, f"github.repos[{i}]")

    lark_raw = _require(data, "lark", "")
    if not isinstance(lark_raw, dict):
        raise ConfigError("配置字段无效: lark 应为对象")
    project_id = _optional_non_empty_str(lark_raw.get("project_id"), "lark.project_id")
    chat_id = _optional_non_empty_str(lark_raw.get("chat_id"), "lark.chat_id")
    if not project_id and not chat_id:
        raise ConfigError("配置至少需要 lark.project_id 或 lark.chat_id")
    keywords = _optional_list(lark_raw.get("keywords"), "lark.keywords")
    if not keywords:
        keywords = ["进度", "阻塞", "评审", "完成", "会议"]
    for i, keyword in enumerate(keywords):
        _require_non_empty_str(keyword, f"lark.keywords[{i}]")
    app_id = _optional_non_empty_str(lark_raw.get("app_id"), "lark.app_id")
    app_secret = _optional_non_empty_str(lark_raw.get("app_secret"), "lark.app_secret")

    notifier_raw = _require(data, "notifier", "")
    if not isinstance(notifier_raw, dict):
        raise ConfigError("配置字段无效: notifier 应为对象")

    email_raw = _require(notifier_raw, "email", "notifier")
    if not isinstance(email_raw, dict):
        raise ConfigError("配置字段无效: notifier.email 应为对象")
    recipients = _optional_list(email_raw.get("recipients"), "notifier.email.recipients")
    for i, recipient in enumerate(recipients):
        _require_non_empty_str(recipient, f"notifier.email.recipients[{i}]")

    lark_bot_raw = _require(notifier_raw, "lark_bot", "notifier")
    if not isinstance(lark_bot_raw, dict):
        raise ConfigError("配置字段无效: notifier.lark_bot 应为对象")
    bot_chat_id = _optional_non_empty_str(
        lark_bot_raw.get("chat_id"),
        "notifier.lark_bot.chat_id",
    )

    return AppConfig(
        team_name=team_name,
        members=members,
        github=GitHubConfig(repos=list(repos)),
        lark=LarkConfig(
            project_id=project_id,
            chat_id=chat_id,
            keywords=list(keywords),
            app_id=app_id,
            app_secret=app_secret,
        ),
        notifier=NotifierConfig(
            email=EmailNotifierConfig(recipients=list(recipients)),
            lark_bot=LarkBotConfig(chat_id=bot_chat_id),
        ),
        raw=data,
    )


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """读取 YAML 配置文件并返回校验后的配置对象。"""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"配置文件不存在: {config_path}")

    try:
        with config_path.open(encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
    except yaml.YAMLError as exc:
        raise ConfigError(f"配置文件 YAML 解析失败: {config_path}", cause=exc) from exc

    if data is None:
        raise ConfigError(f"配置文件为空: {config_path}")

    return validate_config(data)
