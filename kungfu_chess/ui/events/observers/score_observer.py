"""Phase 5 step 3 (final_plan_verified.md section 0.3/7.6): keyed on the
engine's real single-character codes, never translated English words --
the original draft's `PIECE_VALUES = {"pawn": 1, ...}` would always
have returned 0 against `piece.kind == "P"`; this fixes that mismatch
at the source instead of adding a translation layer."""
from __future__ import annotations

from typing import Dict, Optional

from kungfu_chess.ui.events.events import JumpResolvedEvent, MoveResolvedEvent

PIECE_VALUES: Dict[str, int] = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}


class ScoreObserver:
    def __init__(self) -> None:
        self.score = {"w": 0, "b": 0}  # keyed on piece.color's real values

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        self._apply_capture(event.captured_piece_kind, event.piece_color)

    def on_jump_resolved(self, event: JumpResolvedEvent) -> None:
        # Kept for API symmetry with the plan's own blueprint; never
        # actually invoked under the current engine, since jumps never
        # produce a SettlementEvent to begin with (plan section 1).
        self._apply_capture(event.captured_piece_kind, event.piece_color)

    def _apply_capture(self, captured_kind: Optional[str], capturing_color: str) -> None:
        if captured_kind is None:
            return
        self.score[capturing_color] += PIECE_VALUES.get(captured_kind, 0)
