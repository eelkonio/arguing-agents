"""Unit tests for the structured JSON logging module."""

import json
import logging

from multi_agent_debate.logging import JSONFormatter, get_logger, setup_logging


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def _make_record(self, message: str = "hello", level: int = logging.INFO, **extras: object) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        for key, value in extras.items():
            setattr(record, key, value)
        return record

    def test_output_is_valid_json(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("test message")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("test message")
        parsed = json.loads(formatter.format(record))

        assert parsed["level"] == "info"
        assert parsed["service"] == "multi-agent-debate"
        assert "time" in parsed
        assert parsed["message"] == "test message"

    def test_level_is_lowercase(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("warn msg", level=logging.WARNING)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "warning"

    def test_contextual_fields_included_when_present(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record(
            "ctx test",
            session_id="sess-1",
            agent_id="agent-2",
            backend="bedrock",
            request_id="req-3",
        )
        parsed = json.loads(formatter.format(record))

        assert parsed["session_id"] == "sess-1"
        assert parsed["agent_id"] == "agent-2"
        assert parsed["backend"] == "bedrock"
        assert parsed["request_id"] == "req-3"

    def test_contextual_fields_absent_when_not_set(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("plain")
        parsed = json.loads(formatter.format(record))

        for field in ("session_id", "agent_id", "backend", "request_id"):
            assert field not in parsed

    def test_partial_contextual_fields(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("partial", session_id="s1")
        parsed = json.loads(formatter.format(record))

        assert parsed["session_id"] == "s1"
        assert "agent_id" not in parsed

    def test_time_is_iso_format(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("time check")
        parsed = json.loads(formatter.format(record))
        # ISO format contains 'T' separator and ends with timezone info
        assert "T" in parsed["time"]


class TestSetupLogging:
    """Tests for setup_logging."""

    def test_configures_root_logger(self) -> None:
        setup_logging(log_level="debug")
        root = logging.getLogger()

        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_clears_existing_handlers(self) -> None:
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())

        setup_logging(log_level="info")
        assert len(root.handlers) == 1

    def test_defaults_to_settings_log_level(self) -> None:
        # get_settings() defaults to "info"
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO


class TestGetLogger:
    """Tests for get_logger."""

    def test_returns_named_logger(self) -> None:
        logger = get_logger("my.module")
        assert logger.name == "my.module"
        assert isinstance(logger, logging.Logger)
