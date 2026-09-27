"""shared/config.py 单元测试。"""

from pathlib import Path

import pytest
import yaml

from shared.config import load_config, validate_config
from shared.errors import ConfigError

VALID_CONFIG = {
    "team_name": "研发团队",
    "members": [
        {"name": "张三", "github": "zhangsan", "lark": "zhangsan@company.com"},
        {"name": "李四", "github": "lisi-dev", "lark": "lisi@company.com"},
    ],
    "github": {"repos": ["org/repo-a"]},
    "lark": {
        "project_id": "proj-1",
        "chat_id": "chat-1",
        "keywords": ["进度", "阻塞"],
    },
    "notifier": {
        "email": {"recipients": ["leader@company.com"]},
        "lark_bot": {"chat_id": "notify-chat"},
    },
}


def test_validate_config_returns_app_config():
    config = validate_config(VALID_CONFIG)

    assert config.team_name == "研发团队"
    assert len(config.members) == 2
    assert config.members[0].github == "zhangsan"
    assert config.github.repos == ["org/repo-a"]
    assert config.lark.keywords == ["进度", "阻塞"]
    assert config.notifier.email.recipients == ["leader@company.com"]
    assert config.notifier.lark_bot.chat_id == "notify-chat"


def test_load_config_from_yaml_file(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG, allow_unicode=True), encoding="utf-8")

    config = load_config(config_file)

    assert config.team_name == "研发团队"
    assert config.members[1].name == "李四"


def test_load_config_example_file():
    example = Path(__file__).resolve().parents[1] / "config.yaml.example"
    config = load_config(example)

    assert config.team_name
    assert len(config.members) >= 1
    assert all(m.name and m.github and m.lark for m in config.members)


def test_missing_required_field_raises_clear_error():
    data = dict(VALID_CONFIG)
    del data["team_name"]

    with pytest.raises(ConfigError, match="配置缺少必填字段: team_name"):
        validate_config(data)


def test_missing_member_field_raises_clear_error():
    data = {
        **VALID_CONFIG,
        "members": [{"name": "张三", "github": "zhangsan"}],
    }

    with pytest.raises(ConfigError, match=r"配置缺少必填字段: members\[0\]\.lark"):
        validate_config(data)


def test_missing_config_file_raises():
    with pytest.raises(ConfigError, match="配置文件不存在"):
        load_config("not-exists-config.yaml")


def test_empty_members_raises():
    data = {**VALID_CONFIG, "members": []}

    with pytest.raises(ConfigError, match="members"):
        validate_config(data)
