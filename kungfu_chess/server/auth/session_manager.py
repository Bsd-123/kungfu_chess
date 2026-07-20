"""Issues and resolves session tokens (Decision 7): the single source
of identity for every post-login interaction, including reconnection --
no code path re-derives identity from username/password after initial
login. The directive's "username, then username+password" flow is
realized as first-use = registration, repeat-use = verification: this
CLI has no separate "sign up" step, so a username never seen before is
created on the spot with the supplied password, and a known username
must match its stored password."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional

from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.auth.session_repository import SqliteSessionRepository
from kungfu_chess.server.config import AuthenticationConfig

_TOKEN_BYTES = 32


class AuthenticationError(Exception):
    """Raised for an empty username or a known username with a wrong
    password -- the CLI login flow catches this and re-prompts."""


class SessionManager:
    def __init__(self, users: SqliteUserRepository, sessions: SqliteSessionRepository,
                 auth_config: Optional[AuthenticationConfig] = None):
        self._users = users
        self._sessions = sessions
        self._auth_config = auth_config or AuthenticationConfig()

    def login(self, username: str, password: str) -> str:
        if not username:
            raise AuthenticationError("username must not be empty")

        existing = self._users.get_by_username(username)
        if existing is None:
            user = self._users.create_user(username, password)
        else:
            user = self._users.verify_password(username, password)
            if user is None:
                raise AuthenticationError("invalid username or password")

        token = secrets.token_urlsafe(_TOKEN_BYTES)
        self._sessions.create(token, user.id)
        return token

    def resolve(self, token: str) -> Optional[int]:
        """Returns the `user_id` for a live, unexpired token, refreshing
        its `last_seen_at` on every successful resolve -- used both for
        the initial WS handshake and Phase 6 reconnect lookups."""
        session = self._sessions.get(token)
        if session is None:
            return None
        if self._is_expired(session.last_seen_at):
            self._sessions.delete(token)
            return None
        self._sessions.touch(token)
        return session.user_id

    def logout(self, token: str) -> None:
        self._sessions.delete(token)

    def _is_expired(self, last_seen_at: str) -> bool:
        age_s = (datetime.now(timezone.utc) - datetime.fromisoformat(last_seen_at)).total_seconds()
        return age_s > self._auth_config.session_token_lifetime_s
