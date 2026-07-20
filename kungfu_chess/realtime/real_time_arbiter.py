from __future__ import annotations
from typing import List, Optional

from kungfu_chess.config import GameConfig
from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece
from kungfu_chess.realtime.motion import MoveScheduler, PendingMove

__all__ = ["RealTimeArbiter"]


class RealTimeArbiter:
    """Pure timing/scheduling service: schedules moves/jumps with a caller-supplied duration, answers
    busy/target/airborne queries, and reports which motions are due. Never touches a BoardInterface or resolves
    collisions -- that's CollisionHandler's job; GameEngine drives both."""

    def __init__(self, scheduler: Optional[MoveScheduler] = None):
        self._scheduler = scheduler or MoveScheduler()

    # -- conflict queries, consulted before scheduling anything --------
    def is_piece_busy(self, src: Position, clock_ms: int) -> bool:
        return self._scheduler.is_piece_busy(src, clock_ms)

    def is_target_busy(self, dst: Position, clock_ms: int) -> bool:
        return self._scheduler.is_target_busy(dst, clock_ms)

    def is_active_airborne_at(self, cell: Position, clock_ms: int) -> bool:
        return self._scheduler.is_active_airborne_at(cell, clock_ms)

    # -- post-move cooldown feature ---------------------------------------
    def is_cooling_down(self, pos: Position, clock_ms: int) -> bool:
        return self._scheduler.is_cooling_down(pos, clock_ms)

    def cooldown_progress(self, pos: Position, clock_ms: int) -> Optional[float]:
        return self._scheduler.cooldown_progress(pos, clock_ms)

    def has_pending_motions(self) -> bool:
        return bool(self._scheduler.pending_moves)

    def has_active_cooldown(self, clock_ms: int) -> bool:
        return self._scheduler.has_active_cooldown(clock_ms)

    def start_cooldown_for(self, m: PendingMove, landing_square: Position) -> None:
        """Blocks `landing_square` (not necessarily `m.dst`) from new motions for `m.cooldown_ms`; no-op if
        cooldown_ms is 0. Called by GameEngine.settle() once CollisionHandler reports the actual landing square."""
        if m.cooldown_ms > 0:
            self._scheduler.start_cooldown(
                landing_square, m.complete_time + m.cooldown_ms, m.cooldown_ms)

    # -- scheduling ------------------------------------------------------
    def schedule_move(self, src: Position, dst: Position, piece: Piece,
                       clock_ms: int, duration_ms: int,
                       board: BoardInterface, cooldown_ms: int = 0) -> None:
        # Path is computed once via board.get_path and carried on the PendingMove.
        self._scheduler.schedule(PendingMove(
            move_type=GameConfig.MOTION_STATE_MOVE,
            complete_time=clock_ms + duration_ms,
            src=src, dst=dst, piece=piece,
            start_time=clock_ms,
            path=board.get_path(src, dst),
            cooldown_ms=cooldown_ms,
        ))

    def schedule_jump(self, src: Position, piece: Piece,
                       clock_ms: int, duration_ms: int,
                       cooldown_ms: int = 0) -> None:
        self._scheduler.schedule(PendingMove(
            move_type=GameConfig.MOTION_STATE_JUMP,
            complete_time=clock_ms + duration_ms,
            src=src, piece=piece,
            start_time=clock_ms,
            cooldown_ms=cooldown_ms,
        ))

    @property
    def pending_moves(self) -> List[PendingMove]:
        return self._scheduler.pending_moves

    # -- time-synchronized resolution ------------------------------------
    def next_due_motions(self, clock_ms: int) -> List[PendingMove]:
        """Motions due as of `clock_ms`, in strict chronological order (moves and jump landings interleaved, not
        moves-then-jumps, so a late move can't illegally capture atop an already-landed jump). Runs
        `_extend_hovers_for_crossings` first so an extended jump correctly drops out of "due" this call."""
        self._extend_hovers_for_crossings()
        return self._scheduler.due_motions(clock_ms)

    def clear_expired(self, clock_ms: int) -> None:
        """Drops motions no longer pending as of `clock_ms`. Called once by GameEngine.settle() after resolving
        the batch from next_due_motions, so due-but-unresolved motions stay visible to queries until then."""
        self._scheduler.clear_expired(clock_ms)

    # ---- friendly transit dynamically extends a hover --------------------
    def _extend_hovers_for_crossings(self) -> None:
        """A jumper must not land while a friendly slider is still mid-transit across its square: for every
        pending jump, push its complete_time out to at least the complete_time of any same-color move whose path
        crosses the jumper's square as a non-terminal square. Re-run every call since new moves can be scheduled
        after the jump exists; enemy crossings never extend it, and the mover's terminal square is excluded
        (that's a landing question for CollisionHandler, not a timing one)."""
        pending = self._scheduler.pending_moves
        jumps = [m for m in pending if m.move_type == GameConfig.MOTION_STATE_JUMP]
        if not jumps:
            return  # nothing airborne, nothing to extend

        movers = [m for m in pending if m.move_type == GameConfig.MOTION_STATE_MOVE]

        for jump in jumps:
            for mover in movers:
                if mover.piece.color != jump.piece.color:
                    continue  # only a friendly crossing extends the hover
                if jump.src not in mover.path:
                    continue
                index = mover.path.index(jump.src)
                if index == len(mover.path) - 1:
                    continue  # terminal square: a landing question, not timing
                jump.extend_completion_to(mover.complete_time)
