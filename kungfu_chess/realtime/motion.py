from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece


@dataclass
class PendingMove:
    """Value object representing a queued move or jump. Encapsulates the
    field names so no other class needs to know about dict keys, and
    holds the moving Piece as a value object rather than a raw token.

    `start_time` (Phase 4, final_plan_verified.md section 7.5): the
    clock_ms reading at scheduling time. Without it, `0.0 -> 1.0`
    animation progress can't be derived -- only `complete_time` (when a
    motion finishes) was stored before, which only tells you how much
    time is left, not what fraction of the total duration has elapsed.
    Defaults to 0 so this stays backward-compatible with any existing
    caller that constructs a PendingMove positionally without it."""
    move_type: str  # 'move' or 'jump'
    complete_time: int
    src: Position
    piece: Piece
    dst: Optional[Position] = None
    start_time: int = 0


@dataclass
class SettlementEvent:
    """Reports what happened when a single Motion settled. Returned from
    RealTimeArbiter.resolve_due() so GameEngine can apply chess-specific
    *policy* (Rule 11's king-capture -> game_over) without the Arbiter
    itself knowing anything about what a King is."""
    src: Position
    dst: Position
    piece: Piece
    captured_piece: Optional[Piece]


class MoveScheduler:
    """Owns the raw queue of in-flight moves/jumps and answers
    busy/target/airborne membership queries against it. A thin,
    data-only collaborator of RealTimeArbiter: it knows *what* is
    queued, never *when*/*how* motions get resolved into board state."""

    def __init__(self):
        self._pending: List[PendingMove] = []

    def _has_expired(self, complete_time:int , clock_ms: int):
        return complete_time > clock_ms

    def schedule(self, pending_move: PendingMove) -> None:
        self._pending.append(pending_move)

    def is_piece_busy(self, src: Position, clock_ms: int) -> bool:
        return any(m.src == src and self._has_expired(m.complete_time, clock_ms) for m in self._pending)

    def is_target_busy(self, dst: Position, clock_ms: int) -> bool:
        """True if some in-flight *move* (jumps don't count -- they
        don't occupy a destination) is already headed to dst. Backs
        Rule 8 Step 2: two pieces may never simultaneously converge on
        the same destination cell."""
        return any(
            m.move_type == 'move' and m.dst == dst and self._has_expired(m.complete_time, clock_ms)
            for m in self._pending
        )

    def is_active_airborne_at(self, cell: Position, clock_ms: int) -> bool:
        return any(
            m.move_type == 'jump' and m.src == cell and m.complete_time >= clock_ms
            for m in self._pending
        )

    def due_moves(self, clock_ms: int) -> List[PendingMove]:
        due = [m for m in self._pending if m.move_type == 'move' and not self._has_expired(m.complete_time, clock_ms)]
        due.sort(key=lambda m: m.complete_time)
        return due

    def clear_expired(self, clock_ms: int) -> None:
        self._pending = [m for m in self._pending if self._has_expired(m.complete_time, clock_ms)]

    @property
    def pending_moves(self) -> List[PendingMove]:
        return list(self._pending)
