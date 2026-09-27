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


def _require_list(value: Any, field_path: str) -> list[Any]:
    if not isinstance(value, list) or len(value) == 0:
        raise ConfigError(f"配置字段无效（需为非空列表）: {field_path}")
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
    repos = _require_list(_require(github_raw, "repos", "github"), "github.repos")
    for i, repo in enumerate(repos):
        _require_non_empty_str(repo, f"github.repos[{i}]")

    lark_raw = _require(data, "lark", "")
    if not isinstance(lark_raw, dict):
        raise ConfigError("配置字段无效: lark 应为对象")
    project_id = _require_non_empty_str(_require(lark_raw, "project_id", "lark"), "lark.project_id")
    chat_id = _require_non_empty_str(_require(lark_raw, "chat_id", "lark"), "lark.chat_id")
    keywords = _require_list(_require(lark_raw, "keywords", "lark"), "lark.keywords")
    for i, keyword in enumerate(keywords):
        _require_non_empty_str(keyword, f"lark.keywords[{i}]")

    notifier_raw = _require(data, "notifier", "")
    if not isinstance(notifier_raw, dict):
        raise ConfigError("配置字段无效: notifier 应为对象")

    email_raw = _require(notifier_raw, "email", "notifier")
    if not isinstance(email_raw, dict):
        raise ConfigError("配置字段无效: notifier.email 应为对象")
    recipients = _require_list(_require(email_raw, "recipients", "notifier.email"), "notifier.email.recipients")
    for i, recipient in enumerate(recipients):
        _require_non_empty_str(recipient, f"notifier.email.recipients[{i}]")

    lark_bot_raw = _require(notifier_raw, "lark_bot", "notifier")
    if not isinstance(lark_bot_raw, dict):
        raise ConfigError("配置字段无效: notifier.lark_bot 应为对象")
    bot_chat_id = _require_non_empty_str(
        _require(lark_bot_raw, "chat_id", "notifier.lark_bot"),
        "notifier.lark_bot.chat_id",
    )

    return AppConfig(
        team_name=team_name,
        members=members,
        github=GitHubConfig(repos=list(repos)),
        lark=LarkConfig(project_id=project_id, chat_id=chat_id, keywords=list(keywords)),
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
