"""The only module in the codebase allowed to touch raw password bytes
(Decision 3): PBKDF2-HMAC-SHA256 via stdlib `hashlib` -- zero new
dependencies -- with a per-user random salt and an iteration count read
from config, never hardcoded. Isolated behind two functions so the
algorithm can change later without touching call sites."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Tuple

from kungfu_chess.server.config import AuthenticationConfig

_ALGORITHM = "sha256"
_SALT_BYTES = 16


def hash_password(plaintext: str, config: AuthenticationConfig) -> Tuple[str, str]:
    """Returns (password_hash, password_salt) as hex strings, ready for
    the `users` table -- a fresh random salt every call."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_ALGORITHM, plaintext.encode("utf-8"), salt, config.pbkdf2_iterations)
    return digest.hex(), salt.hex()


def verify_password(plaintext: str, password_hash: str, password_salt: str,
                     config: AuthenticationConfig) -> bool:
    salt = bytes.fromhex(password_salt)
    digest = hashlib.pbkdf2_hmac(_ALGORITHM, plaintext.encode("utf-8"), salt, config.pbkdf2_iterations)
    return hmac.compare_digest(digest.hex(), password_hash)
