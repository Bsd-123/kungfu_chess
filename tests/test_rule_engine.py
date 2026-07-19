import pytest

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.rules.rule_engine import RuleEngine, MoveValidation
from kungfu_chess.rules.rule_registry import create_default_chess_registry
from kungfu_chess.rules.promotion_rules import ConditionalPromotionRule, last_rank_trigger


def board3():
    b = ArrayBoard([['.'] * 3 for _ in range(3)])
    return b


def engine():
    return RuleEngine(create_default_chess_registry())


def test_move_validation_bool_true():
    assert bool(MoveValidation(True, 'ok')) is True


def test_move_validation_bool_false():
    assert bool(MoveValidation(False, 'nope')) is False


def test_validate_move_outside_board_src():
    e = engine()
    board = board3()
    piece = Piece(color='w', type='K')
    result = e.validate_move(board, piece, Position(-1, 0), Position(0, 0))
    assert result.is_valid is False
    assert result.reason == 'outside_board'


def test_validate_move_outside_board_dst():
    e = engine()
    board = board3()
    piece = Piece(color='w', type='K')
    result = e.validate_move(board, piece, Position(0, 0), Position(9, 9))
    assert result.is_valid is False
    assert result.reason == 'outside_board'


def test_validate_move_empty_source():
    e = engine()
    board = board3()
    result = e.validate_move(board, None, Position(0, 0), Position(1, 1))
    assert result.is_valid is False
    assert result.reason == 'empty_source'


def test_validate_move_friendly_destination():
    e = engine()
    board = board3()
    board.set_piece_at(Position(1, 1), Piece(color='w', type='P'))
    piece = Piece(color='w', type='K')
    result = e.validate_move(board, piece, Position(0, 0), Position(1, 1))
    assert result.is_valid is False
    assert result.reason == 'friendly_destination'


def test_validate_move_illegal_piece_move():
    e = engine()
    board = board3()
    piece = Piece(color='w', type='K')
    result = e.validate_move(board, piece, Position(0, 0), Position(2, 2))
    assert result.is_valid is False
    assert result.reason == 'illegal_piece_move'


def test_validate_move_ok():
    e = engine()
    board = board3()
    piece = Piece(color='w', type='K')
    result = e.validate_move(board, piece, Position(0, 0), Position(1, 1))
    assert result.is_valid is True
    assert result.reason == 'ok'
    assert bool(result) is True


def test_resolve_arrival_piece_default_no_promotion():
    e = engine()
    board = board3()
    piece = Piece(color='w', type='P')
    result = e.resolve_arrival_piece(piece, Position(0, 0), board)
    assert result == piece


def test_resolve_arrival_piece_with_promotion_rule_injected():
    e = RuleEngine(create_default_chess_registry(),
                    promotion_rule=ConditionalPromotionRule(trigger=last_rank_trigger))
    board = board3()
    piece = Piece(color='w', type='P')
    result = e.resolve_arrival_piece(piece, Position(0, 0), board)
    assert result.type == 'Q'
