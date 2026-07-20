from __future__ import annotations
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from kungfu_chess.config import GameConfig
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece


@dataclass
class PendingMove:
    """A queued move or jump. start_time is used to derive 0.0->1.0 animation progress; path is precomputed
    src->dst squares (unused for jumps); seq is a scheduling-order tiebreaker for equal complete_time; cooldown_ms
    is how long (ms) the landing square blocks new motions after settling (0 = none)."""
    move_type: str  # 'move' or 'jump'
    complete_time: int
    src: Position
    piece: Piece
    dst: Optional[Position] = None
    start_time: int = 0
    path: List[Position] = field(default_factory=list)
    seq: int = 0
    cooldown_ms: int = 0

    def extend_completion_to(self, new_time: int) -> None:
        """Pushes complete_time later only, never earlier."""

        if new_time > self.complete_time:
            self.complete_time = new_time


@dataclass
class SettlementEvent:
    """Outcome of a settled motion, returned by CollisionHandler so GameEngine can apply chess policy (e.g. win
    conditions) without CollisionHandler knowing what a King is. dst may differ from requested_dst if truncated
    by a block/capture; reverted is True only for the defensive no-capture jump fallback."""
    src: Position
    dst: Position
    piece: Piece
    captured_piece: Optional[Piece]
    move_type: str = GameConfig.MOTION_STATE_MOVE
    requested_dst: Optional[Position] = None
    reverted: bool = False

    # Derived properties so this structurally satisfies SettlementDataInterface (settlement_data.py).
    @property
    def piece_color(self) -> str:
        return self.piece.color

    @property
    def piece_kind(self) -> str:
        return self.piece.kind

    @property
    def captured_piece_kind(self) -> Optional[str]:
        return self.captured_piece.kind if self.captured_piece is not None else None


class MoveScheduler:
    """Owns the queue of in-flight moves/jumps and answers busy/target/airborne queries; doesn't resolve motions
    into board state."""

    def __init__(self):
        self._pending: List[PendingMove] = []
        self._seq_counter = itertools.count()

        # (until_ms, duration_ms) per Position; overwritten on re-settle, so no pruning needed.
        self._cooldowns: Dict[Position, Tuple[int, int]] = {}

    def _is_still_pending(self, complete_time: int, clock_ms: int) -> bool:
        """True while a motion is still in flight (not yet due)."""
        return complete_time > clock_ms

    def schedule(self, pending_move: PendingMove) -> None:
        pending_move.seq = next(self._seq_counter)
        self._pending.append(pending_move)

    def is_piece_busy(self, src: Position, clock_ms: int) -> bool:
        return any(m.src == src and self._is_still_pending(m.complete_time, clock_ms)
                   for m in self._pending)

    def is_target_busy(self, dst: Position, clock_ms: int) -> bool:
        """True if an in-flight move is already headed to dst (jumps don't occupy a destination)."""
        return any(
            m.move_type == GameConfig.MOTION_STATE_MOVE and m.dst == dst
            and self._is_still_pending(m.complete_time, clock_ms)
            for m in self._pending
        )

    def is_active_airborne_at(self, cell: Position, clock_ms: int) -> bool:
        return any(
            m.move_type == GameConfig.MOTION_STATE_JUMP and m.src == cell
            and m.complete_time >= clock_ms
            for m in self._pending
        )

    def due_moves(self, clock_ms: int) -> List[PendingMove]:
        due = [m for m in self._pending
               if m.move_type == GameConfig.MOTION_STATE_MOVE
               and not self._is_still_pending(m.complete_time, clock_ms)]
        due.sort(key=lambda m: m.complete_time)
        return due

    def due_jumps(self, clock_ms: int) -> List[PendingMove]:
        """Mirror of due_moves for jump landings."""
        due = [m for m in self._pending
               if m.move_type == GameConfig.MOTION_STATE_JUMP
               and not self._is_still_pending(m.complete_time, clock_ms)]
        due.sort(key=lambda m: m.complete_time)
        return due

    def due_motions(self, clock_ms: int) -> List[PendingMove]:
        """All due moves and jump landings merged into one chronological list (complete_time, then seq); must
        stay merged rather than moves-then-jumps, or a late move could illegally overwrite an earlier-landed jump."""
        due = [m for m in self._pending if not self._is_still_pending(m.complete_time, clock_ms)]
        due.sort(key=lambda m: (m.complete_time, m.seq))
        return due

    def clear_expired(self, clock_ms: int) -> None:
        self._pending = [m for m in self._pending if self._is_still_pending(m.complete_time, clock_ms)]

    @property
    def pending_moves(self) -> List[PendingMove]:
        return list(self._pending)

    # -- post-move cooldown ------------------------------------------------
    def start_cooldown(self, pos: Position, until_ms: int, duration_ms: int) -> None:
        """Records that pos can't host a new motion until until_ms."""
        self._cooldowns[pos] = (until_ms, duration_ms)

    def is_cooling_down(self, pos: Position, clock_ms: int) -> bool:
        entry = self._cooldowns.get(pos)
        return entry is not None and entry[0] > clock_ms

    def has_active_cooldown(self, clock_ms: int) -> bool:
        return any(until_ms > clock_ms for until_ms, _ in self._cooldowns.values())

    def cooldown_progress(self, pos: Position, clock_ms: int) -> Optional[float]:
        """0.0 (just settled) -> 1.0 (finished) elapsed fraction, or None if pos isn't cooling down."""
        entry = self._cooldowns.get(pos)
        if entry is None:
            return None
        until_ms, duration_ms = entry
        if until_ms <= clock_ms or duration_ms <= 0:
            return None
        remaining_ms = until_ms - clock_ms
        elapsed_ms = duration_ms - remaining_ms
        return max(0.0, min(1.0, elapsed_ms / duration_ms))