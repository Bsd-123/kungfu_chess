import pytest

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.rules.promotion_rules import (
    PromotionRule,
    NoPromotionRule,
    ConditionalPromotionRule,
    LastRankQueenPromotionRule,
    last_rank_trigger,
    at_positions,
)


def board3():
    return ArrayBoard([['.'] * 3 for _ in range(3)])


def test_promotion_rule_is_abstract():
    with pytest.raises(TypeError):
        PromotionRule()


def test_no_promotion_rule_returns_same_piece():
    board = board3()
    piece = Piece(color='w', type='P')
    result = NoPromotionRule().apply(piece, Position(0, 0), board)
    assert result == piece


def test_last_rank_trigger_true_at_row_zero():
    board = board3()
    assert last_rank_trigger(Position(0, 1), board) is True


def test_last_rank_trigger_true_at_last_row():
    board = board3()
    assert last_rank_trigger(Position(2, 1), board) is True


def test_last_rank_trigger_false_in_middle():
    board = board3()
    assert last_rank_trigger(Position(1, 1), board) is False


def test_at_positions_trigger():
    trigger = at_positions([Position(1, 1), Position(2, 2)])
    board = board3()
    assert trigger(Position(1, 1), board) is True
    assert trigger(Position(0, 0), board) is False


def test_conditional_promotion_rule_promotes_pawn_at_last_rank():
    board = board3()
    piece = Piece(color='w', type='P', id='p1', state='moving')
    rule = ConditionalPromotionRule()
    result = rule.apply(piece, Position(0, 1), board)
    assert result.type == 'Q'
    assert result.color == 'w'
    assert result.id == 'p1'
    assert result.cell == Position(0, 1)
    assert result.state == 'moving'


def test_conditional_promotion_rule_does_not_promote_non_promotable_type():
    board = board3()
    piece = Piece(color='w', type='K')
    rule = ConditionalPromotionRule()
    result = rule.apply(piece, Position(0, 1), board)
    assert result == piece


def test_conditional_promotion_rule_does_not_promote_when_trigger_false():
    board = board3()
    piece = Piece(color='w', type='P')
    rule = ConditionalPromotionRule()
    result = rule.apply(piece, Position(1, 1), board)
    assert result == piece


def test_conditional_promotion_rule_custom_promote_to_and_types():
    board = board3()
    piece = Piece(color='b', type='N')
    rule = ConditionalPromotionRule(promotable_types=('N',), promote_to='R')
    result = rule.apply(piece, Position(2, 0), board)
    assert result.type == 'R'


def test_last_rank_queen_promotion_rule_factory():
    board = board3()
    piece = Piece(color='w', type='P')
    rule = LastRankQueenPromotionRule()
    result = rule.apply(piece, Position(0, 0), board)
    assert result.type == 'Q'
