from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Iterable

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece

# Decides whether a piece settling at `dst` should be transformed.
PromotionTrigger = Callable[[Position, BoardInterface], bool]


def last_rank_trigger(dst: Position, board: BoardInterface) -> bool:
    """Default chess trigger: the destination is the first or last rank."""
    return dst[0] in (0, board.nrows - 1)


def at_positions(positions: Iterable[Position]) -> PromotionTrigger:
    """Trigger factory that fires only on a fixed set of tiles."""
    target = set(positions)

    def trigger(dst: Position, board: BoardInterface) -> bool:
        return dst in target

    return trigger


class PromotionRule(ABC):
    """Strategy interface applied to a piece after it settles onto its destination square."""

    @abstractmethod
    def apply(self, piece: Piece, dst: Position, board: BoardInterface) -> Piece:
        ...


class NoPromotionRule(PromotionRule):
    def apply(self, piece, dst, board):
        return piece


class ConditionalPromotionRule(PromotionRule):
    """Transforms a piece of one of `promotable_types` into `promote_to`
    whenever `trigger(dst, board)` returns True."""

    def __init__(self, trigger: PromotionTrigger = last_rank_trigger,
                 promotable_types: Iterable[str] = ('P',), promote_to: str = 'Q'):
        self._trigger = trigger
        self._promotable_types = set(promotable_types)
        self._promote_to = promote_to

    def apply(self, piece, dst, board):
        if piece.type in self._promotable_types and self._trigger(dst, board):
            return Piece(color=piece.color, type=self._promote_to, id=piece.id,
                         cell=dst, state=piece.state)
        return piece


def LastRankQueenPromotionRule(promotable_types: Iterable[str] = ('P',),
                                promote_to: str = 'Q') -> ConditionalPromotionRule:
    """Standard chess rule: a pawn reaching the back rank becomes a queen."""
    return ConditionalPromotionRule(trigger=last_rank_trigger,
                                     promotable_types=promotable_types,
                                     promote_to=promote_to)
