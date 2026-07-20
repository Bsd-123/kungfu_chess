import pytest

from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.auth.db import open_connection
from kungfu_chess.server.auth.session_manager import AuthenticationError, SessionManager
from kungfu_chess.server.auth.session_repository import SqliteSessionRepository
from kungfu_chess.server.config import AuthenticationConfig

_AUTH_CONFIG = AuthenticationConfig(pbkdf2_iterations=1000)


def make_manager(auth_config=None):
    conn = open_connection(":memory:")
    users = SqliteUserRepository(conn, _AUTH_CONFIG)
    sessions = SqliteSessionRepository(conn)
    return SessionManager(users, sessions, auth_config or _AUTH_CONFIG), users, sessions


def test_login_with_a_new_username_registers_the_account():
    manager, users, _ = make_manager()
    token = manager.login("alice", "hunter2")
    assert token
    assert users.get_by_username("alice") is not None


def test_login_with_known_username_and_correct_password_succeeds():
    manager, _, _ = make_manager()
    manager.login("alice", "hunter2")
    token = manager.login("alice", "hunter2")
    assert token


def test_login_with_known_username_and_wrong_password_raises():
    manager, _, _ = make_manager()
    manager.login("alice", "hunter2")
    with pytest.raises(AuthenticationError):
        manager.login("alice", "wrong-password")


def test_login_with_empty_username_raises():
    manager, _, _ = make_manager()
    with pytest.raises(AuthenticationError):
        manager.login("", "hunter2")


def test_resolve_returns_the_user_id_for_a_live_token():
    manager, users, _ = make_manager()
    token = manager.login("alice", "hunter2")
    user = users.get_by_username("alice")
    assert manager.resolve(token) == user.id


def test_resolve_returns_none_for_unknown_token():
    manager, _, _ = make_manager()
    assert manager.resolve("nonexistent-token") is None


def test_resolve_returns_none_and_deletes_an_expired_token():
    manager, _, sessions = make_manager(AuthenticationConfig(pbkdf2_iterations=1000,
                                                               session_token_lifetime_s=0))
    token = manager.login("alice", "hunter2")
    import time
    time.sleep(0.01)
    assert manager.resolve(token) is None
    assert sessions.get(token) is None


def test_logout_deletes_the_session():
    manager, _, sessions = make_manager()
    token = manager.login("alice", "hunter2")
    manager.logout(token)
    assert sessions.get(token) is None
    assert manager.resolve(token) is None
