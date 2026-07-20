from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.auth.db import open_connection
from kungfu_chess.server.auth.session_repository import SqliteSessionRepository
from kungfu_chess.server.config import AuthenticationConfig

_AUTH_CONFIG = AuthenticationConfig(pbkdf2_iterations=1000)


def make_repositories():
    conn = open_connection(":memory:")
    users = SqliteUserRepository(conn, _AUTH_CONFIG)
    sessions = SqliteSessionRepository(conn)
    return users, sessions


def test_get_returns_none_for_unknown_token():
    _, sessions = make_repositories()
    assert sessions.get("nonexistent-token") is None


def test_create_and_get_round_trip():
    users, sessions = make_repositories()
    user = users.create_user("alice", "hunter2")
    session = sessions.create("token-123", user.id)
    assert sessions.get("token-123") == session
    assert session.user_id == user.id


def test_touch_updates_last_seen_at():
    users, sessions = make_repositories()
    user = users.create_user("alice", "hunter2")
    original = sessions.create("token-123", user.id)
    sessions.touch("token-123")
    updated = sessions.get("token-123")
    assert updated.last_seen_at >= original.last_seen_at


def test_delete_removes_the_session():
    users, sessions = make_repositories()
    user = users.create_user("alice", "hunter2")
    sessions.create("token-123", user.id)
    sessions.delete("token-123")
    assert sessions.get("token-123") is None


def test_purge_expired_removes_only_stale_sessions():
    users, sessions = make_repositories()
    user = users.create_user("alice", "hunter2")
    sessions.create("fresh-token", user.id)
    stale = sessions.create("stale-token", user.id)
    conn = sessions._conn
    conn.execute("UPDATE sessions SET last_seen_at = '2000-01-01T00:00:00+00:00' WHERE token = ?",
                 (stale.token,))
    conn.commit()

    removed = sessions.purge_expired(lifetime_s=3600)

    assert removed == 1
    assert sessions.get("fresh-token") is not None
    assert sessions.get("stale-token") is None
