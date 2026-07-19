import pytest

from kungfu_chess.model.piece import Piece
from kungfu_chess.rules.win_condition import (
    WinConditionRule,
    CapturedTypeWinCondition,
    king_capture_win_condition,
)


def test_win_condition_rule_is_abstract():
    with pytest.raises(TypeError):
        WinConditionRule()


def test_default_winning_types_is_king():
    cond = CapturedTypeWinCondition()
    attacker = Piece(color='w', type='Q')
    king = Piece(color='b', type='K')
    assert cond.check(attacker, king) is True


def test_non_winning_capture_returns_false():
    cond = CapturedTypeWinCondition()
    attacker = Piece(color='w', type='Q')
    pawn = Piece(color='b', type='P')
    assert cond.check(attacker, pawn) is False


def test_custom_winning_capture_types():
    cond = CapturedTypeWinCondition(winning_capture_types=('R', 'R'))
    attacker = Piece(color='w', type='Q')
    rook = Piece(color='b', type='R')
    assert cond.check(attacker, rook) is True


def test_king_capture_win_condition_factory():
    cond = king_capture_win_condition()
    attacker = Piece(color='w', type='P')
    king = Piece(color='b', type='K')
    assert cond.check(attacker, king) is True
    queen = Piece(color='b', type='Q')
    assert cond.check(attacker, queen) is False
