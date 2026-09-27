"""shared/errors.py 单元测试。"""

import pytest

from shared.errors import AppError, CollectorError, ConfigError, GeneratorError, NotifierError


def test_custom_exceptions_are_app_error_subclasses():
    assert issubclass(CollectorError, AppError)
    assert issubclass(GeneratorError, AppError)
    assert issubclass(NotifierError, AppError)
    assert issubclass(ConfigError, AppError)


def test_exception_message_and_cause():
    cause = ValueError("timeout")
    err = CollectorError("GitHub API 失败", cause=cause)

    assert err.message == "GitHub API 失败"
    assert err.cause is cause
    assert "GitHub API 失败" in str(err)
    assert "timeout" in str(err)


@pytest.mark.parametrize(
    "exc_cls",
    [CollectorError, GeneratorError, NotifierError, ConfigError],
)
def test_exceptions_are_raisable(exc_cls):
    with pytest.raises(exc_cls, match="boom"):
        raise exc_cls("boom")
