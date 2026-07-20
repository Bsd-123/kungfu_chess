"""get_logger() caches by name for the life of the process (so every
server module sharing a name reuses one rotating file handler) --
each test here therefore uses a fresh unique logger name, or its
config would be ignored in favor of whichever config first registered
that name."""
from __future__ import annotations

import json
import logging
import uuid

from kungfu_chess.server.config import LoggingConfig
from kungfu_chess.server.logging.structured_logger import get_logger, log_event


def _config(tmp_path, **overrides):
    defaults = dict(log_file_path=str(tmp_path / "server.ndjson"), max_bytes=5_000_000, backup_count=3)
    defaults.update(overrides)
    return LoggingConfig(**defaults)


def _unique_name() -> str:
    return f"test-{uuid.uuid4().hex}"


def test_log_event_writes_one_json_line_with_message_and_fields(tmp_path):
    config = _config(tmp_path)
    logger = get_logger(_unique_name(), config)

    log_event(logger, "move accepted", game_id="g1", connection_id="c1")
    for handler in logger.handlers:
        handler.flush()

    lines = config.log_file_path and open(config.log_file_path, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["message"] == "move accepted"
    assert record["game_id"] == "g1"
    assert record["connection_id"] == "c1"
    assert record["level"] == "INFO"


def test_each_call_appends_its_own_line(tmp_path):
    config = _config(tmp_path)
    logger = get_logger(_unique_name(), config)

    log_event(logger, "first")
    log_event(logger, "second")
    for handler in logger.handlers:
        handler.flush()

    lines = open(config.log_file_path, encoding="utf-8").read().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["message"] == "first"
    assert json.loads(lines[1])["message"] == "second"


def test_session_token_field_is_redacted_not_written_raw(tmp_path):
    config = _config(tmp_path)
    logger = get_logger(_unique_name(), config)
    raw_token = "super-secret-session-token-value"

    log_event(logger, "reconnected", session_token=raw_token)
    for handler in logger.handlers:
        handler.flush()

    content = open(config.log_file_path, encoding="utf-8").read()
    assert raw_token not in content
    record = json.loads(content.splitlines()[0])
    assert record["session_token"] != raw_token


def test_password_hash_field_is_redacted():
    from kungfu_chess.server.logging.structured_logger import _redact
    assert _redact("abcdefgh12345678") != "abcdefgh12345678"


def test_non_sensitive_fields_pass_through_unredacted(tmp_path):
    config = _config(tmp_path)
    logger = get_logger(_unique_name(), config)

    log_event(logger, "room created", room_id="AB12C")
    for handler in logger.handlers:
        handler.flush()

    record = json.loads(open(config.log_file_path, encoding="utf-8").read().splitlines()[0])
    assert record["room_id"] == "AB12C"


def test_get_logger_reuses_the_same_logger_for_the_same_name(tmp_path):
    name = _unique_name()
    config = _config(tmp_path)
    first = get_logger(name, config)
    second = get_logger(name, config)
    assert first is second
    assert len(first.handlers) == 1  # not re-added on the second call


def test_log_file_rotates_once_the_size_cap_is_exceeded(tmp_path):
    config = _config(tmp_path, max_bytes=300, backup_count=2)
    logger = get_logger(_unique_name(), config)

    for i in range(50):
        log_event(logger, "padding-" * 5, sequence=i)
    for handler in logger.handlers:
        handler.flush()

    rotated = list(tmp_path.glob("server.ndjson.*"))
    assert len(rotated) >= 1
