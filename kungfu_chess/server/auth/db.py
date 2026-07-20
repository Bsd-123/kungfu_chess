"""SQLite connection + schema bootstrap for the auth layer. Scoped
strictly to `users` and `sessions` (Decision 10) -- no match/move/room
history tables. WAL mode is enabled so concurrent games finishing at
the same time (Phase 4 rating writes, session `last_seen_at` refreshes)
don't hit `database is locked` errors."""
from __future__ import annotations

import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    rating INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    issued_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
"""


def open_connection(db_path: str) -> sqlite3.Connection:
    """Opens (creating if absent) the auth database and ensures both
    tables exist -- the "thin migration/bootstrap script" the plan
    calls for, small enough to not warrant a separate migration tool.

    `check_same_thread=False`: repository calls are offloaded via
    `asyncio.to_thread` (server/app.py), which runs them on a thread
    pool worker, not the connection's creating thread. SQLite's own
    library is compiled thread-safe (serialized mode) in the builds
    Python ships, so sharing one connection across threads is safe for
    this server's access pattern (single-statement reads/writes, no
    cross-thread read-modify-write races); WAL mode above already
    handles the concurrent-readers-plus-one-writer case."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn
