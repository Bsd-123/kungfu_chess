from __future__ import annotations
from typing import List

from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.motion_gate import MotionGate

__all__ = ["LegalDestinationsCalculator"]


class LegalDestinationsCalculator:
    """Computes every square a click on `source` could send that piece to right now
    (everywhere `request_move` would accept, plus `source` itself if `request_jump`
    would). Read-only query, re-deriving legality the same way `request_move` does so
    the highlighted set never drifts. `validate_move` is shape-only and ignores path
    blocking, so this class additionally checks current occupancy along the path."""

    def __init__(self, state: GameState, rule_engine: RuleEngine, motion_gate: MotionGate):
        self._state = state
        self._rule_engine = rule_engine
        self._motion_gate = motion_gate

    def compute(self, source: Position) -> List[Position]:
        piece = self._state.board.get_piece_at(source)
        if piece is None or self._motion_gate.blocked_reason(source) is not None:
            return []

        board = self._state.board
        destinations: List[Position] = []
        for row in range(self._state.nrows):
            for col in range(self._state.ncols):
                dst = Position(row, col)
                if dst == source or self._state.is_target_busy(dst):
                    continue
                validation = self._rule_engine.validate_move(board, piece, source, dst)
                if not validation.is_valid:
                    continue

                # path[:-1] = squares strictly between source and dst (empty for a
                # knight); if any is occupied, dst isn't reachable this instant.
                path = board.get_path(source, dst)
                if any(not board.is_empty_at(sq) for sq in path[:-1]):
                    continue

                destinations.append(dst)

        # request_jump only needs MotionGate, already checked above.
        destinations.append(source)
        return destinations
