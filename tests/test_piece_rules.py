import pytest

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.rules.piece_rules import (
    MovementRule,
    BaseMovementRule,
    KingMovementRule,
    QueenMovementRule,
    RookMovementRule,
    BishopMovementRule,
    KnightMovementRule,
    PawnMovementRule,
    default_pawn_direction_provider,
)


def empty_board(n=8):
    return ArrayBoard([['.'] * n for _ in range(n)])


def test_movement_rule_is_abstract():
    with pytest.raises(TypeError):
        MovementRule()


def test_base_movement_rule_is_abstract():
    with pytest.raises(TypeError):
        BaseMovementRule()


def test_base_movement_rule_rejects_staying_put():
    board = empty_board()
    piece = Piece(color='w', type='K')
    assert KingMovementRule().is_legal_move(board, piece, Position(0, 0), Position(0, 0)) is False


def test_base_movement_rule_rejects_friendly_capture():
    board = empty_board()
    board.set_piece_at(Position(0, 1), Piece(color='w', type='P'))
    piece = Piece(color='w', type='K')
    assert KingMovementRule().is_legal_move(board, piece, Position(0, 0), Position(0, 1)) is False


def test_base_movement_rule_allows_enemy_capture_when_shape_legal():
    board = empty_board()
    board.set_piece_at(Position(0, 1), Piece(color='b', type='P'))
    piece = Piece(color='w', type='K')
    assert KingMovementRule().is_legal_move(board, piece, Position(0, 0), Position(0, 1)) is True


@pytest.mark.parametrize("dst,expected", [
    (Position(1, 1), True), (Position(1, 0), True), (Position(0, 1), True),
    (Position(2, 0), False), (Position(2, 2), False),
])
def test_king_movement(dst, expected):
    board = empty_board()
    piece = Piece(color='w', type='K')
    assert KingMovementRule().is_legal_move(board, piece, Position(0, 0), dst) is expected


@pytest.mark.parametrize("dst,expected", [
    (Position(0, 5), True), (Position(5, 0), True), (Position(1, 1), False),
])
def test_rook_movement(dst, expected):
    board = empty_board()
    piece = Piece(color='w', type='R')
    assert RookMovementRule().is_legal_move(board, piece, Position(0, 0), dst) is expected


@pytest.mark.parametrize("dst,expected", [
    (Position(3, 3), True), (Position(1, 1), True), (Position(0, 5), False),
])
def test_bishop_movement(dst, expected):
    board = empty_board()
    piece = Piece(color='w', type='B')
    assert BishopMovementRule().is_legal_move(board, piece, Position(0, 0), dst) is expected


@pytest.mark.parametrize("dst,expected", [
    (Position(0, 5), True), (Position(3, 3), True), (Position(1, 2), False),
])
def test_queen_movement(dst, expected):
    board = empty_board()
    piece = Piece(color='w', type='Q')
    assert QueenMovementRule().is_legal_move(board, piece, Position(0, 0), dst) is expected


@pytest.mark.parametrize("dst,expected", [
    (Position(2, 1), True), (Position(1, 2), True), (Position(2, 2), False), (Position(1, 1), False),
])
def test_knight_movement(dst, expected):
    board = empty_board()
    piece = Piece(color='w', type='N')
    assert KnightMovementRule().is_legal_move(board, piece, Position(0, 0), dst) is expected


def test_default_pawn_direction_provider_white():
    board = empty_board()
    direction, start_row = default_pawn_direction_provider('w', board)
    assert direction == -1
    assert start_row == board.nrows - 2


def test_default_pawn_direction_provider_black():
    board = empty_board()
    direction, start_row = default_pawn_direction_provider('b', board)
    assert direction == 1
    assert start_row == 1


def test_pawn_single_forward_move_onto_empty_square():
    board = empty_board()
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(6, 0), Position(5, 0)) is True


def test_pawn_single_forward_move_blocked():
    board = empty_board()
    board.set_piece_at(Position(5, 0), Piece(color='b', type='P'))
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(6, 0), Position(5, 0)) is False


def test_pawn_double_forward_from_start_row():
    board = empty_board()
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(6, 0), Position(4, 0)) is True


def test_pawn_double_forward_not_from_start_row_illegal():
    board = empty_board()
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(5, 0), Position(3, 0)) is False


def test_pawn_diagonal_capture_legal_when_enemy_present():
    board = empty_board()
    board.set_piece_at(Position(5, 1), Piece(color='b', type='P'))
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(6, 0), Position(5, 1)) is True


def test_pawn_diagonal_move_without_capture_illegal():
    board = empty_board()
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(6, 0), Position(5, 1)) is False


def test_pawn_sideways_move_illegal():
    board = empty_board()
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(6, 0), Position(6, 1)) is False


def test_pawn_backwards_move_illegal():
    board = empty_board()
    piece = Piece(color='w', type='P')
    assert PawnMovementRule().is_legal_move(board, piece, Position(6, 0), Position(7, 0)) is False


def test_pawn_custom_direction_provider_injected():
    def flipped(color, board):
        return 1, 0  # everyone moves "down" starting row 0

    board = empty_board()
    piece = Piece(color='w', type='P')
    rule = PawnMovementRule(direction_provider=flipped)
    assert rule.is_legal_move(board, piece, Position(0, 0), Position(1, 0)) is True
    assert rule.is_legal_move(board, piece, Position(0, 0), Position(2, 0)) is True
