"""Structured logging facade (Decision 11): NDJSON, one JSON object per
line, written to a local rotating file only -- no external aggregation.
Every server module should log through `log_event`, never an ad hoc
`print()` or a bare `logger.info(...)`, so format, destination, and
redaction all live in exactly one place (DRY/SRP).

Redaction discipline: session tokens and password hashes must never
appear raw in a log line. `log_event` redacts any field whose *name* is
a known-sensitive one before it ever reaches the formatter -- callers
don't have to remember to do this themselves at each call site."""
from __future__ import annotations

import json
import logging
import logging.handlers
from typing import Any, Dict, Optional

from kungfu_chess.server.config import LoggingConfig

_SENSITIVE_FIELDS = frozenset({
    "session_token", "token", "password", "password_hash", "password_salt",
})

_configured_loggers: Dict[str, logging.Logger] = {}


class _NdjsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        return json.dumps(payload)


def get_logger(name: str, config: Optional[LoggingConfig] = None) -> logging.Logger:
    """Returns a NDJSON-configured logger for `name`, creating its
    rotating file handler once and reusing it on every subsequent call
    -- the shared logger factory every server module is meant to use
    instead of configuring `logging` ad hoc."""
    if name in _configured_loggers:
        return _configured_loggers[name]

    config = config or LoggingConfig()
    logger = logging.getLogger(name)
    logger.setLevel(config.level)
    logger.propagate = False

    handler = logging.handlers.RotatingFileHandler(
        config.log_file_path, maxBytes=config.max_bytes, backupCount=config.backup_count)
    handler.setFormatter(_NdjsonFormatter())
    logger.addHandler(handler)

    _configured_loggers[name] = logger
    return logger


def log_event(logger: logging.Logger, message: str, level: int = logging.INFO, **fields: Any) -> None:
    """The one call site every server module should use: `message` is a
    short human-readable summary, `fields` are the structured, greppable
    payload (session token, connection id, room/game id, message_id --
    see master_work_plan.md's Correlation ID propagation). Any field
    named like a secret is redacted before formatting."""
    redacted = {key: (_redact(value) if key in _SENSITIVE_FIELDS else value)
                for key, value in fields.items()}
    logger.log(level, message, extra={"fields": redacted})


def _redact(value: Any) -> str:
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"
