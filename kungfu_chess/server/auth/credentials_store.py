"""User account persistence (Decision 10: users + rating only, no
history tables). `SqliteUserRepository` is the only place outside
`password_hasher.py` that touches password hashing, and the only place
in the codebase that runs SQL against `users` -- callers only ever see
`User`, never a raw row."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from kungfu_chess.server.auth.password_hasher import hash_password, verify_password
from kungfu_chess.server.config import AuthenticationConfig, RatingConfig


@dataclass(frozen=True)
class User:
    id: int
    username: str
    rating: int


class UsernameTakenError(Exception):
    """Raised on a duplicate-username race (Phase 3 risk: two clients
    registering the same name simultaneously) -- surfaced as a clean,
    catchable error rather than an unhandled sqlite3.IntegrityError."""


class SqliteUserRepository:
    def __init__(self, conn: sqlite3.Connection, auth_config: AuthenticationConfig,
                 rating_config: Optional[RatingConfig] = None):
        self._conn = conn
        self._auth_config = auth_config
        self._rating_config = rating_config or RatingConfig()

    def get_by_username(self, username: str) -> Optional[User]:
        row = self._conn.execute(
            "SELECT id, username, rating FROM users WHERE username = ?", (username,)
        ).fetchone()
        return User(*row) if row is not None else None

    def get_by_id(self, user_id: int) -> Optional[User]:
        row = self._conn.execute(
            "SELECT id, username, rating FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return User(*row) if row is not None else None

    def update_rating(self, user_id: int, new_rating: int) -> None:
        """The only write this repository performs outside registration
        (Decision 10: rating is the one mutable, ongoing-persistence
        column on `users`); called by RatingUpdateService after a
        completed game."""
        self._conn.execute("UPDATE users SET rating = ? WHERE id = ?", (new_rating, user_id))
        self._conn.commit()

    def create_user(self, username: str, plaintext_password: str) -> User:
        password_hash, password_salt = hash_password(plaintext_password, self._auth_config)
        try:
            cursor = self._conn.execute(
                "INSERT INTO users (username, password_hash, password_salt, rating, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, password_salt, self._rating_config.base_rating,
                 datetime.now(timezone.utc).isoformat()))
        except sqlite3.IntegrityError as exc:
            raise UsernameTakenError(username) from exc
        self._conn.commit()
        return User(id=cursor.lastrowid, username=username, rating=self._rating_config.base_rating)

    def verify_password(self, username: str, plaintext_password: str) -> Optional[User]:
        """Looks up `username` and checks `plaintext_password` against
        its stored hash in one call; returns the User on success, None
        on either an unknown username or a wrong password (deliberately
        not distinguishing the two to callers, to avoid username
        enumeration via a different failure mode)."""
        row = self._conn.execute(
            "SELECT id, username, rating, password_hash, password_salt FROM users WHERE username = ?",
            (username,)).fetchone()
        if row is None:
            return None
        user_id, uname, rating, password_hash, password_salt = row
        if not verify_password(plaintext_password, password_hash, password_salt, self._auth_config):
            return None
        return User(id=user_id, username=uname, rating=rating)
