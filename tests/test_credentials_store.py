import pytest

from kungfu_chess.server.auth.credentials_store import SqliteUserRepository, UsernameTakenError
from kungfu_chess.server.auth.db import open_connection
from kungfu_chess.server.config import AuthenticationConfig, RatingConfig

_AUTH_CONFIG = AuthenticationConfig(pbkdf2_iterations=1000)


def make_repository(rating_config=None):
    conn = open_connection(":memory:")
    return SqliteUserRepository(conn, _AUTH_CONFIG, rating_config)


def test_get_by_username_returns_none_when_absent():
    repo = make_repository()
    assert repo.get_by_username("nobody") is None


def test_create_user_is_seeded_at_configured_base_rating():
    repo = make_repository(RatingConfig(base_rating=1200))
    user = repo.create_user("alice", "hunter2")
    assert user.username == "alice"
    assert user.rating == 1200
    assert repo.get_by_username("alice") == user


def test_create_user_with_duplicate_username_raises():
    repo = make_repository()
    repo.create_user("alice", "hunter2")
    with pytest.raises(UsernameTakenError):
        repo.create_user("alice", "different-password")


def test_verify_password_accepts_correct_credentials():
    repo = make_repository()
    created = repo.create_user("alice", "hunter2")
    verified = repo.verify_password("alice", "hunter2")
    assert verified == created


def test_verify_password_rejects_wrong_password():
    repo = make_repository()
    repo.create_user("alice", "hunter2")
    assert repo.verify_password("alice", "wrong-password") is None


def test_verify_password_rejects_unknown_username():
    repo = make_repository()
    assert repo.verify_password("nobody", "hunter2") is None
