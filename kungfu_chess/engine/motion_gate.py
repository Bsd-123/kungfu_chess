from __future__ import annotations
from typing import Optional

from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.engine.move_reasons import MoveReasons

__all__ = ["MotionGate"]


class MotionGate:
    """Shared game_over/busy/cooldown eligibility gate used by `request_move`,
    `request_jump`, and `legal_destinations`. Checks in order: game over ->
    GAME_OVER, square already has an active motion -> MOTION_IN_PROGRESS,
    square cooling down -> COOLDOWN. Read-only; never mutates state."""

    def __init__(self, state: GameState):
        self._state = state

    def blocked_reason(self, pos: Position) -> Optional[str]:
        if self._state.game_over:
            return MoveReasons.GAME_OVER
        if self._state.is_piece_busy(pos):
            return MoveReasons.MOTION_IN_PROGRESS
        if self._state.is_cooling_down(pos):
            return MoveReasons.COOLDOWN
        return None
