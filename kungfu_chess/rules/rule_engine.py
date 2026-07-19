from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece
from kungfu_chess.rules.promotion_rules import NoPromotionRule, PromotionRule
from kungfu_chess.rules.rule_registry import RuleRegistry


@dataclass(frozen=True)
class MoveValidation:
    """Result of a move-legality check. `reason` is `"ok"` or a stable code
    (`"outside_board"`, `"empty_source"`, `"friendly_destination"`, `"illegal_piece_move"`)."""

    is_valid: bool
    reason: str

    def __bool__(self) -> bool:
        return self.is_valid


_OK = MoveValidation(True, "ok")


class RuleEngine:
    """Answers whether a piece may legally move from src to dst; never mutates state.
    Delegates shape legality to a RuleRegistry and promotion to a PromotionRule."""

    def __init__(self, rule_registry: RuleRegistry,
                 promotion_rule: Optional[PromotionRule] = None):
        self._rule_registry = rule_registry
        self._promotion_rule = promotion_rule or NoPromotionRule()

    def validate_move(self, board: BoardInterface, piece: Optional[Piece],
                       src: Position, dst: Position) -> MoveValidation:
        """Legality check; bounds are validated before any MovementRule runs to avoid
        IndexErrors, and `piece=None` yields "empty_source" instead of requiring
        callers to special-case it."""
        if not board.is_within_bounds(src) or not board.is_within_bounds(dst):
            return MoveValidation(False, "outside_board")

        if piece is None:
            return MoveValidation(False, "empty_source")

        dest_piece = board.get_piece_at(dst)
        if dest_piece is not None and dest_piece.color == piece.color:
            return MoveValidation(False, "friendly_destination")

        if not self._rule_registry.is_legal_move(board, piece, src, dst):
            return MoveValidation(False, "illegal_piece_move")

        return _OK

    def resolve_arrival_piece(self, piece: Piece, dst: Position,
                               board: BoardInterface) -> Piece:
        """What `piece` becomes once it settles at `dst` (e.g. promotion), or unchanged."""
        return self._promotion_rule.apply(piece, dst, board)
