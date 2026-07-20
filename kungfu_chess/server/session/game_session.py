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
from typing import Awaitable, Callable, List, Optional

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


class GameSession:
    def __init__(self, game_id: str, engine: GameEngine, event_bus: EventBus,
                 network_config: NetworkConfig, send_to_connection: SendToConnection,
                 clock: Callable[[], float] = time.monotonic):
        self.game_id = game_id
        self.engine = engine
        self.event_bus = event_bus
        self.network_config = network_config
        self._send_to_connection = send_to_connection
        self._clock = clock
        self.white_connection: Optional[object] = None
        self.black_connection: Optional[object] = None
        self._tick_task: Optional[asyncio.Task] = None

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

    def add_player(self, connection: object) -> PlayerRole:
        """First joiner is White, second is Black (per the directive)."""
        if self.white_connection is None:
            self.white_connection = connection
            return PlayerRole.WHITE
        if self.black_connection is None:
            self.black_connection = connection
            return PlayerRole.BLACK
        raise SessionFullError(self.game_id)

    def remove_player(self, connection: object) -> None:
        if self.white_connection is connection:
            self.white_connection = None
        elif self.black_connection is connection:
            self.black_connection = None

    @property
    def connections(self) -> List[object]:
        return [c for c in (self.white_connection, self.black_connection) if c is not None]

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
        for connection in self.connections:
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
