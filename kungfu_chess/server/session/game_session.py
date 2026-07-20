"""The aggregate root for one in-progress game: the single entity that
owns everything about that game's runtime lifecycle -- the GameEngine
instance, its per-game domain EventBus, the asyncio tick task, and the
two players' connection references. Nothing outside GameSession should
hold a second copy of any of this; `ConnectionRegistry` maps
`connection -> (GameSession, role)` rather than assembling a parallel
view of "what's true about this game" from scattered state."""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Awaitable, Callable, Dict, List, Optional

from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.engine.move_reasons import MoveReasons
from kungfu_chess.engine.move_result import MoveResult
from kungfu_chess.model.position import Position
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.protocol import Envelope, make_envelope
from kungfu_chess.server.session.session_reasons import SessionReasons
from kungfu_chess.server.snapshot_codec import snapshot_to_dict
from kungfu_chess.ui.events.event_bus import EventBus

SendToConnection = Callable[[object, Envelope], Awaitable[None]]


class PlayerRole(Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def piece_color(self) -> str:
        return 'w' if self is PlayerRole.WHITE else 'b'


class SessionFullError(Exception):
    """Raised when a third connection tries to occupy a GameSession's
    player slots. The max-2-for-Play cap (Decision 6) is enforced one
    layer up, in matchmaking/room admission (Phase 4/5) -- this is the
    structural guard for GameSession's own two slots."""

    def __init__(self, game_id: str):
        super().__init__(f"GameSession {game_id!r} already has two players")
        self.game_id = game_id


class SpectatorCapError(Exception):
    """Raised when a connection tries to join as a spectator once this
    GameSession already holds `spectator_cap` of them (Decision 9's
    21st-spectator rejection). Room-specific admission policy (Phase 5)
    still lives in `room_manager.py` -- this is the structural guard for
    GameSession's own spectator list, mirroring `SessionFullError`."""

    def __init__(self, game_id: str, cap: int):
        super().__init__(f"GameSession {game_id!r} already has {cap} spectators")
        self.game_id = game_id


class GameSession:
    def __init__(self, game_id: str, engine: GameEngine, event_bus: EventBus,
                 network_config: NetworkConfig, send_to_connection: SendToConnection,
                 clock: Callable[[], float] = time.monotonic, spectator_cap: int = 20):
        self.game_id = game_id
        self.engine = engine
        self.event_bus = event_bus
        self.network_config = network_config
        self._send_to_connection = send_to_connection
        self._clock = clock
        self._spectator_cap = spectator_cap
        self.white_connection: Optional[object] = None
        self.black_connection: Optional[object] = None
        self.spectators: List[object] = []

        # Account identity per color (Phase 3's session tokens resolve to
        # a user_id one layer up, in the connection handshake). Persists
        # for the GameSession's lifetime, independent of connection
        # churn, so a disconnect never loses "who was playing this
        # color" -- RatingUpdateService (Phase 4) and forfeit handling
        # (Phase 6) both need it after the socket is long gone. None for
        # an anonymous/offline-style session, in which case rating
        # simply does not apply (see RatingUpdateService).
        self.white_user_id: Optional[int] = None
        self.black_user_id: Optional[int] = None

        # Guards against applying an ELO update twice for the same game
        # (a retried or double-fired GameEndedEvent) -- checked and
        # flipped by RatingUpdateService, discarded with the rest of
        # this GameSession once it's torn down (not persisted).
        self.rating_applied: bool = False

        self._tick_task: Optional[asyncio.Task] = None

        # Decision 7: a disconnected player's 20-second reconnect grace
        # timer, keyed by role and stored here rather than in a separate
        # parallel map (see disconnect_monitor.py's module docstring) --
        # `role in self._disconnect_tasks` is exactly "this color has a
        # pending disconnect, still resumable."
        self._disconnect_tasks: Dict[PlayerRole, asyncio.Task] = {}

    # -- player admission (structural only; capacity policy lives in the
    # caller -- see module docstring and SessionFullError) --------------
    def role_for(self, connection: object) -> Optional[PlayerRole]:
        if connection is self.white_connection:
            return PlayerRole.WHITE
        if connection is self.black_connection:
            return PlayerRole.BLACK
        return None

    def is_full(self) -> bool:
        return self.white_connection is not None and self.black_connection is not None

    def add_player(self, connection: object, user_id: Optional[int] = None) -> PlayerRole:
        """First joiner is White, second is Black (per the directive).
        `user_id` is optional -- omitted by callers that don't yet have
        an authenticated identity for this connection (e.g. today's
        Phase 2 ad hoc join flow); rating simply won't apply to those
        sessions (see RatingUpdateService)."""
        if self.white_connection is None:
            self.white_connection = connection
            self.white_user_id = user_id
            return PlayerRole.WHITE
        if self.black_connection is None:
            self.black_connection = connection
            self.black_user_id = user_id
            return PlayerRole.BLACK
        raise SessionFullError(self.game_id)

    def remove_player(self, connection: object) -> None:
        if self.white_connection is connection:
            self.white_connection = None
        elif self.black_connection is connection:
            self.black_connection = None

    def rebind_player(self, role: PlayerRole, connection: object) -> None:
        """Reconnection (Decision 7): re-seats `role` with a new socket,
        same color assignment, same GameEngine reference -- the game
        resumes from its exact current state. Does not touch
        `white_user_id`/`black_user_id`, which never changed."""
        if role is PlayerRole.WHITE:
            self.white_connection = connection
        else:
            self.black_connection = connection

    # -- disconnect grace period (Decision 7) -----------------------------
    def mark_disconnected(self, role: PlayerRole, grace_period_ms: int,
                           on_expire: Callable[[], None]) -> None:
        """Starts (or restarts) `role`'s reconnect grace timer. The
        engine is never paused for this -- a piece's in-flight motion or
        cooldown keeps counting down in real time, consistent with this
        being a real-time game, not a turn-based one."""
        self.cancel_disconnect(role)

        async def _grace_timer() -> None:
            try:
                await asyncio.sleep(grace_period_ms / 1000)
            except asyncio.CancelledError:
                return
            self._disconnect_tasks.pop(role, None)
            on_expire()

        self._disconnect_tasks[role] = asyncio.ensure_future(_grace_timer())

    def cancel_disconnect(self, role: PlayerRole) -> bool:
        """Cancels a pending grace timer (a reconnect arrived in time).
        Returns whether one was actually pending."""
        task = self._disconnect_tasks.pop(role, None)
        if task is not None:
            task.cancel()
            return True
        return False

    def has_pending_disconnect(self, role: PlayerRole) -> bool:
        return role in self._disconnect_tasks

    @property
    def connections(self) -> List[object]:
        """Players only -- deliberately excludes spectators. Both the
        Phase 2 disconnect-cleanup check and Phase 5's room teardown
        (Decision 9: destroyed the moment both *players* have left,
        regardless of how many spectators remain) key off this list."""
        return [c for c in (self.white_connection, self.black_connection) if c is not None]

    # -- spectator admission (structural only; Room-specific policy,
    # like the room-full "explicit message" wording, lives in
    # room_manager.py -- see SpectatorCapError) --------------------------
    def add_spectator(self, connection: object) -> None:
        if len(self.spectators) >= self._spectator_cap:
            raise SpectatorCapError(self.game_id, self._spectator_cap)
        self.spectators.append(connection)

    def remove_spectator(self, connection: object) -> None:
        if connection in self.spectators:
            self.spectators.remove(connection)

    def is_spectator(self, connection: object) -> bool:
        return connection in self.spectators

    @property
    def all_connections(self) -> List[object]:
        """Players + spectators -- the actual broadcast target for
        snapshots and relayed domain events (spectators watch the same
        stream as players, read-only)."""
        return self.connections + self.spectators

    # -- command handling: membership AND color-authorization, both
    # checked server-side (never trust the client to only send its own
    # color's moves) --------------------------------------------------
    def handle_move_command(self, connection: object, source: Position,
                             destination: Position) -> MoveResult:
        role = self.role_for(connection)
        if role is None:
            return MoveResult(False, SessionReasons.NOT_A_PLAYER)
        piece = self.engine.board.get_piece_at(source)
        if piece is None:
            return MoveResult(False, SessionReasons.NO_PIECE_AT_SOURCE)
        if piece.color != role.piece_color:
            return MoveResult(False, SessionReasons.WRONG_COLOR)
        return self.engine.request_move(source, destination)

    def handle_jump_command(self, connection: object, position: Position) -> MoveResult:
        role = self.role_for(connection)
        if role is None:
            return MoveResult(False, SessionReasons.NOT_A_PLAYER)
        piece = self.engine.board.get_piece_at(position)
        if piece is None:
            return MoveResult(False, SessionReasons.NO_PIECE_AT_SOURCE)
        if piece.color != role.piece_color:
            return MoveResult(False, SessionReasons.WRONG_COLOR)
        accepted = self.engine.request_jump(position)
        return MoveResult(accepted, MoveReasons.OK if accepted else MoveReasons.MOTION_IN_PROGRESS)

    # -- envelope transmission -------------------------------------------
    async def send_to(self, connection: object, envelope: Envelope) -> None:
        await self._send_to_connection(connection, envelope)

    async def broadcast(self, envelope: Envelope) -> None:
        for connection in self.all_connections:
            await self._send_to_connection(connection, envelope)

    # -- snapshot transmission (Snapshot Synchronization Strategy) -------
    async def send_snapshot_to(self, connection: object) -> None:
        """Initial full snapshot sent once, immediately, on a new
        connection attaching to this session (join/reconnect/spectator)."""
        envelope = make_envelope("snapshot", snapshot_to_dict(self.engine.snapshot()),
                                  self.network_config)
        await self.send_to(connection, envelope)

    async def broadcast_snapshot(self) -> None:
        envelope = make_envelope("snapshot", snapshot_to_dict(self.engine.snapshot()),
                                  self.network_config)
        await self.broadcast(envelope)

    # -- tick loop lifecycle: one asyncio.Task per game (Decision 1) ----
    def start(self) -> None:
        if self._tick_task is None:
            self._tick_task = asyncio.ensure_future(self._tick_loop())

    def stop(self) -> None:
        if self._tick_task is not None:
            self._tick_task.cancel()
            self._tick_task = None
        # A torn-down session must never let a stray forfeit fire later.
        for role in list(self._disconnect_tasks):
            self.cancel_disconnect(role)

    async def _tick_loop(self) -> None:
        """Mirrors `ui/game_loop.py::run_loop`'s shape (advance clock,
        settle, broadcast) but only does either while the engine reports
        activity -- a settled, idle board does no per-interval work."""
        last = self._clock()
        interval_s = self.network_config.tick_interval_ms / 1000
        try:
            while True:
                await asyncio.sleep(interval_s)
                now = self._clock()
                dt_ms = max(0, int((now - last) * 1000))
                last = now
                if self.engine.has_activity():
                    self.engine.advance_clock(dt_ms)
                    await self.broadcast_snapshot()
        except asyncio.CancelledError:
            pass
