"""Structured JSON logger setup."""

import json
import logging
from datetime import datetime, timezone

from multi_agent_debate.config import get_settings

_CONTEXTUAL_FIELDS = ("session_id", "agent_id", "backend", "request_id")


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Every entry contains at minimum: ``level``, ``service``, ``time``, and
    ``message``.  Contextual fields (``session_id``, ``agent_id``,
    ``backend``, ``request_id``) are included when present on the log record.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "level": record.levelname.lower(),
            "service": "multi-agent-debate",
            "time": datetime.now(timezone.utc).isoformat(),
            "message": record.getMessage(),
        }
        for field in _CONTEXTUAL_FIELDS:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)
        return json.dumps(log_entry)


def setup_logging(log_level: str | None = None) -> None:
    """Configure the root logger with :class:`JSONFormatter`.

    Parameters
    ----------
    log_level:
        Python log-level name (e.g. ``"info"``, ``"debug"``).  When *None*
        the level is read from :func:`~multi_agent_debate.config.get_settings`.
    """
    if log_level is None:
        log_level = get_settings().log_level

    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # Remove any existing handlers to avoid duplicate output.
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given *name*.

    This is a thin convenience wrapper around :func:`logging.getLogger` that
    keeps import paths consistent across the codebase.
    """
    return logging.getLogger(name)
