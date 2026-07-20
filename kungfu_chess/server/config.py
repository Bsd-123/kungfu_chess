"""Server-side config, split by concern (see master_work_plan.md's
Cross-Cutting Compliance Notes) rather than one growing dataclass. Each
phase's server modules depend only on the specific config type they
need -- `server/protocol.py` takes a `NetworkConfig`, not the whole
`ServerConfig`."""
from __future__ import annotations
import logging
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
    # default).
    base_rating: int = 1200

    # Decision 4: a single fixed K-factor, no variable/dynamic scaling.
    k_factor: int = 32


@dataclass(frozen=True)
class MatchmakingConfig:
    # Decision 13: this band is fixed for the whole search window -- it
    # never widens the longer a player waits.
    elo_band: int = 100

    # Decision 5: on expiry the client returns to idle; no auto-retry.
    timeout_s: float = 60.0


@dataclass(frozen=True)
class RoomConfig:
    # Decision 8: 4-6 character alphanumeric codes. A fixed length
    # within that range keeps generation simple without losing anything
    # the decision requires.
    room_code_length: int = 5

    # Decision 9: the 21st spectator join attempt is rejected outright.
    spectator_cap: int = 20


@dataclass(frozen=True)
class ReliabilityConfig:
    # Decision 7: 20 seconds to reconnect and resume the exact same game
    # state before an auto-forfeit.
    disconnect_grace_period_ms: int = 20_000


@dataclass(frozen=True)
class LoggingConfig:
    # Decision 11: NDJSON, local files only. Rotation is a required
    # implementation detail (Phase 6 risk: unbounded log growth), not an
    # optional nice-to-have.
    log_file_path: str = "kungfu_chess_server.ndjson"
    max_bytes: int = 5_000_000
    backup_count: int = 5
    level: int = logging.INFO


@dataclass(frozen=True)
class ServerConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    game: GameConfig = field(default_factory=GameConfig)
    authentication: AuthenticationConfig = field(default_factory=AuthenticationConfig)
    rating: RatingConfig = field(default_factory=RatingConfig)
    matchmaking: MatchmakingConfig = field(default_factory=MatchmakingConfig)
    room: RoomConfig = field(default_factory=RoomConfig)
    reliability: ReliabilityConfig = field(default_factory=ReliabilityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
