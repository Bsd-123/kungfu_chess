"""Client-side stand-in for `GameEngine` when playing over the
network. Exposes the exact surface `Controller` and
`ui/game_loop.py::run_loop` already use against a local `GameEngine`
(`board`, `selected`, `request_move`, `request_jump`, `snapshot`,
`advance_clock`, `legal_destinations`, `clock_ms`, `game_over`) so
neither module needs to know whether it's talking to a local engine or
a remote server (Strict Encapsulation) -- this is the payoff of
Controller never having called engine methods for their return values."""
from __future__ import annotations

from typing import List, Optional

from kungfu_chess.model.position import Position
from kungfu_chess.network.network_client import NetworkClient
from kungfu_chess.network.remote_board_mirror import RemoteBoardMirror
from kungfu_chess.view.game_snapshot import GameSnapshot


class RemoteGameProxy:
    def __init__(self, network_client: NetworkClient, initial_snapshot: GameSnapshot):
        self._network_client = network_client
        self._snapshot = initial_snapshot
        self.board = RemoteBoardMirror()
        self.selected: Optional[Position] = None
        self.game_over: bool = initial_snapshot.game_over
        self.winner_color: Optional[str] = initial_snapshot.winner
        self.clock_ms: int = 0

    # -- command forwarding: fire-and-forget, server is authoritative --
    def request_move(self, source: Position, destination: Position) -> None:
        self._network_client.request_move(source, destination)

    def request_jump(self, position: Position) -> None:
        self._network_client.request_jump(position)

    # -- read-only surface used by ui/game_loop.py::run_loop -----------
    def snapshot(self) -> GameSnapshot:
        return self._snapshot

    def advance_clock(self, ms: int) -> None:
        """No-op: the server is the authoritative clock. Cosmetic
        interpolation comes entirely from the periodically-broadcast
        `GameSnapshot`, not a locally-advanced clock (Phase 2 Risk:
        "server is authoritative for legality/state, client owns purely
        cosmetic timing")."""

    def legal_destinations(self, source: Position) -> List[Position]:
        """No client-side rule engine in remote mode yet -- no
        destination-highlight support until a future phase adds one."""
        return []

    # -- state updates, applied by the caller's per-frame poll loop ----
    def apply_snapshot(self, snapshot: GameSnapshot) -> None:
        self._snapshot = snapshot
        self.game_over = snapshot.game_over
        self.winner_color = snapshot.winner
