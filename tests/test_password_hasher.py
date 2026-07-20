from kungfu_chess.server.auth.password_hasher import hash_password, verify_password
from kungfu_chess.server.config import AuthenticationConfig

_CONFIG = AuthenticationConfig(pbkdf2_iterations=1000)  # low iteration count, tests only


def test_verify_password_accepts_correct_plaintext():
    password_hash, password_salt = hash_password("hunter2", _CONFIG)
    assert verify_password("hunter2", password_hash, password_salt, _CONFIG) is True


def test_verify_password_rejects_wrong_plaintext():
    password_hash, password_salt = hash_password("hunter2", _CONFIG)
    assert verify_password("wrong-password", password_hash, password_salt, _CONFIG) is False


def test_hash_password_uses_a_fresh_random_salt_each_call():
    hash_a, salt_a = hash_password("same-password", _CONFIG)
    hash_b, salt_b = hash_password("same-password", _CONFIG)
    assert salt_a != salt_b
    assert hash_a != hash_b


def test_password_is_never_stored_as_plaintext():
    password_hash, password_salt = hash_password("hunter2", _CONFIG)
    assert "hunter2" not in password_hash
    assert "hunter2" not in password_salt
