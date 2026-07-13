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
    """Result shape mandated by Spec §8. `reason` is always present:
    `"ok"` for a legal move, otherwise a stable, machine-readable code
    (`"outside_board"`, `"empty_source"`, `"friendly_destination"`,
    `"illegal_piece_move"`). Kept as a tiny frozen dataclass rather than
    a bare bool so callers (and tests) can branch on *why* a move was
    rejected without re-deriving it themselves."""

    is_valid: bool
    reason: str

    def __bool__(self) -> bool:
        # Non-breaking convenience: any existing/future call site that
        # still does `if rule_engine.validate_move(...):` keeps working,
        # since MoveValidation is now truthy/falsy exactly like the old
        # plain bool was.
        return self.is_valid


_OK = MoveValidation(True, "ok")


class RuleEngine:
    """The Validation Layer (Rule 7): a specialized Validation Service
    that answers, definitively, whether a piece may legally move from
    src to dst -- including whether that arrival would trigger a
    Promotion. It never performs the move and never mutates state; it
    only judges.

    It delegates piece-shape legality to the Strategy-pattern
    RuleRegistry (Rule 6) and end-of-move transformation to a
    PromotionRule, composing them without duplicating either's logic."""

    def __init__(self, rule_registry: RuleRegistry,
                 promotion_rule: Optional[PromotionRule] = None):
        self._rule_registry = rule_registry
        self._promotion_rule = promotion_rule or NoPromotionRule()

    def validate_move(self, board: BoardInterface, piece: Optional[Piece],
                       src: Position, dst: Position) -> MoveValidation:
        """Definitive legality answer for a requested move, as a
        MoveValidation carrying a stable reason code (Spec §8). Bounds
        are checked here, defense-in-depth, before any MovementRule ever
        touches src/dst -- callers that reach the facade with an
        out-of-bounds coordinate (from any path, not just the normal
        PositionArgParser-validated one) get a clean rejection instead
        of an IndexError surfacing from deep inside a shape check.

        `piece` may be None (e.g. GameEngine looked up an empty source
        cell); RuleEngine owns the "empty_source" verdict itself per
        spec, rather than requiring callers to special-case it earlier."""
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
        """What `piece` becomes once it settles at `dst` -- e.g. a
        Promotion trigger firing -- or the same piece, unchanged."""
        return self._promotion_rule.apply(piece, dst, board)
