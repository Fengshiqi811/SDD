"""shared/logger.py 单元测试。"""

import io
import json
import logging

from shared.logger import JsonLinesFormatter, get_logger


def test_json_lines_formatter_output():
    formatter = JsonLinesFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    line = formatter.format(record)
    payload = json.loads(line)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload
    assert "\n" not in line


def test_get_logger_emits_json_lines():
    logger = get_logger("daily-report-test-json")
    logger.handlers.clear()

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLinesFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.error("推送失败", extra={"channel": "email"})
    payload = json.loads(stream.getvalue().strip())

    assert payload["level"] == "ERROR"
    assert payload["message"] == "推送失败"
    assert payload["channel"] == "email"
