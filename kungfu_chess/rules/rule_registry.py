from __future__ import annotations
from typing import Dict, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.rules.piece_rules import (
    MovementRule,
    KingMovementRule,
    QueenMovementRule,
    RookMovementRule,
    BishopMovementRule,
    KnightMovementRule,
    PawnMovementRule,
)
from kungfu_chess.model.piece import Piece


class RuleRegistry:
    """Maps a piece-type identifier to its MovementRule strategy."""

    def __init__(self, rules: Optional[Dict[str, MovementRule]] = None):
        self._rules: Dict[str, MovementRule] = dict(rules) if rules else {}

    def register(self, piece_type: str, rule: MovementRule) -> None:
        self._rules[piece_type] = rule

    def get_rule(self, piece_type: str) -> Optional[MovementRule]:
        return self._rules.get(piece_type)

    def is_legal_move(self, board: BoardInterface, piece: Piece,
                       src: Position, dst: Position) -> bool:
        rule = self.get_rule(piece.type)
        if rule is None:
            return False
        return rule.is_legal_move(board, piece, src, dst)


def create_default_chess_registry() -> RuleRegistry:
    """Factory producing the standard chess piece set."""
    registry = RuleRegistry()
    registry.register('K', KingMovementRule())
    registry.register('Q', QueenMovementRule())
    registry.register('R', RookMovementRule())
    registry.register('B', BishopMovementRule())
    registry.register('N', KnightMovementRule())
    registry.register('P', PawnMovementRule())
    return registry
