"""Logging configuration.

Configures stdlib logging for the whole app. Two formats:

- ``plain`` (default): human-readable single-line output suitable for
  local dev and docker-compose logs.
- ``json``: one JSON object per log record suitable for log-aggregation
  pipelines (Loki, Datadog, CloudWatch, etc.).

Configured via env:

- ``LOG_LEVEL``: debug | info | warning | error (default info)
- ``LOG_FORMAT``: plain | json (default plain)

Uvicorn's own loggers are routed through the same configuration so
access logs and app logs share one pipeline.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Minimal structured JSON formatter — keeps stdlib-only deps."""

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Any extras passed via logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = repr(value)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "info", fmt: str = "plain") -> None:
    """Configure the root logger and mirror uvicorn's loggers into it.

    Safe to call multiple times — existing handlers are cleared first
    so hot reloads or test sessions don't accumulate duplicates.
    """
    level_num = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-5s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level_num)

    # Uvicorn creates its own named loggers with independent handlers —
    # strip those so records bubble up to our root handler instead.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvlogger = logging.getLogger(name)
        uvlogger.handlers.clear()
        uvlogger.propagate = True
