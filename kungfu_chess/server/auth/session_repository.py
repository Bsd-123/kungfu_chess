"""Session-token persistence (Decision 10), paired with
`SqliteUserRepository` via the same repository pattern. The token is
the sole identity carried across a reconnect (Decision 7) -- `get`/
`touch` are the only lookups Phase 6's reconnect handler will need."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class Session:
    token: str
    user_id: int
    issued_at: str
    last_seen_at: str


class SqliteSessionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(self, token: str, user_id: int) -> Session:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO sessions (token, user_id, issued_at, last_seen_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, now))
        self._conn.commit()
        return Session(token=token, user_id=user_id, issued_at=now, last_seen_at=now)

    def get(self, token: str) -> Optional[Session]:
        row = self._conn.execute(
            "SELECT token, user_id, issued_at, last_seen_at FROM sessions WHERE token = ?",
            (token,)).fetchone()
        return Session(*row) if row is not None else None

    def touch(self, token: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE token = ?",
            (datetime.now(timezone.utc).isoformat(), token))
        self._conn.commit()

    def delete(self, token: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        self._conn.commit()

    def purge_expired(self, lifetime_s: int) -> int:
        """Deletes every session not seen within `lifetime_s` seconds;
        returns the number removed. The retention policy the Phase 3
        risk section calls for, so this table doesn't grow unbounded."""
        cutoff_iso = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - lifetime_s, timezone.utc).isoformat()
        cursor = self._conn.execute("DELETE FROM sessions WHERE last_seen_at < ?", (cutoff_iso,))
        self._conn.commit()
        return cursor.rowcount
