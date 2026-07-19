from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Optional

from kungfu_chess.model.piece import Piece

"""Win-condition strategy, injected into GameEngine and consulted once per settlement."""


class WinConditionRule(ABC):
    """Strategy interface, consulted once per settled motion when a capture occurred."""

    @abstractmethod
    def check(self, piece: Piece, captured_piece: Piece) -> bool:
        """True if this capture ends the game."""


class CapturedTypeWinCondition(WinConditionRule):
    """Game ends the instant a piece of one of `winning_capture_types` is captured."""

    def __init__(self, winning_capture_types: Iterable[str] = ('K',)):
        self._winning_capture_types = set(winning_capture_types)

    def check(self, piece: Piece, captured_piece: Piece) -> bool:
        return captured_piece.type in self._winning_capture_types


def king_capture_win_condition() -> CapturedTypeWinCondition:
    """Standard chess rule: capturing the King ends the game."""
    return CapturedTypeWinCondition(('K',))
