"""Server-side config, split by concern (see master_work_plan.md's
Cross-Cutting Compliance Notes) rather than one growing dataclass. Each
phase's server modules depend only on the specific config type they
need -- `server/protocol.py` takes a `NetworkConfig`, not the whole
`ServerConfig`."""
from __future__ import annotations
from dataclasses import dataclass, field

from kungfu_chess.config import GameConfig


@dataclass(frozen=True)
class NetworkConfig:
    host: str = "localhost"
    port: int = 8765

    # Fixed wire-format version; a future breaking change branches on
    # this rather than requiring a flag day.
    protocol_version: int = 1

    # Frames larger than this are rejected as malformed (server/protocol.py).
    max_message_bytes: int = 65536

    # How long a message_id is remembered for duplicate-request replay
    # (server/protocol.py's idempotency cache).
    idempotency_window_ms: int = 5000

    # Tick loop interval while a GameSession has activity; a settled,
    # idle board does no per-interval work (GameEngine.has_activity()).
    tick_interval_ms: int = 50


@dataclass(frozen=True)
class AuthenticationConfig:
    # hashlib.pbkdf2_hmac('sha256', ...) rounds (Decision 3); read from
    # config so the cost factor can be tuned without touching call sites.
    pbkdf2_iterations: int = 210_000

    # Sliding session-token expiry: a token not seen for this long is
    # treated as gone (Phase 3 risk: "sessions table doesn't grow
    # unbounded"). Reconnection (Decision 7) resets this on every use.
    session_token_lifetime_s: int = 7 * 24 * 3600

    db_path: str = "kungfu_chess.db"


@dataclass(frozen=True)
class RatingConfig:
    # Seed rating for a brand-new account (Decision 10's `users.rating`
    # default). Phase 4 extends this dataclass with k_factor and the
    # matchmaking ELO band -- kept minimal here since only base_rating
    # is needed until matchmaking exists.
    base_rating: int = 1200


@dataclass(frozen=True)
class ServerConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    game: GameConfig = field(default_factory=GameConfig)
    authentication: AuthenticationConfig = field(default_factory=AuthenticationConfig)
    rating: RatingConfig = field(default_factory=RatingConfig)
