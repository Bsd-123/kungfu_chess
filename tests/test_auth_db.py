from kungfu_chess.server.auth.db import open_connection


def test_open_connection_creates_users_and_sessions_tables():
    conn = open_connection(":memory:")
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"users", "sessions"}.issubset(tables)


def test_open_connection_is_idempotent():
    conn = open_connection(":memory:")
    # Re-running the bootstrap against an already-initialized connection
    # (mirrors a real process re-opening an existing db file) must not
    # raise on the CREATE TABLE statements.
    from kungfu_chess.server.auth.db import _SCHEMA
    conn.executescript(_SCHEMA)


def test_foreign_keys_pragma_is_enabled():
    conn = open_connection(":memory:")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
