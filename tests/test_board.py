import pytest

from kungfu_chess.model.board import ArrayBoard, BoardInterface
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position


def make_board(rows=None):
    if rows is None:
        rows = [
            list('wR wN wB wQ wK wB wN wR'.split()),
            list('wP wP wP wP wP wP wP wP'.split()),
            list('. . . . . . . .'.split()),
            list('. . . . . . . .'.split()),
            list('. . . . . . . .'.split()),
            list('. . . . . . . .'.split()),
            list('bP bP bP bP bP bP bP bP'.split()),
            list('bR bN bB bQ bK bB bN bR'.split()),
        ]
    return ArrayBoard(rows)


def test_nrows_ncols():
    b = make_board()
    assert b.nrows == 8
    assert b.ncols == 8


def test_empty_board_dimensions():
    b = ArrayBoard([])
    assert b.nrows == 0
    assert b.ncols == 0


def test_is_within_bounds():
    b = make_board()
    assert b.is_within_bounds(Position(0, 0))
    assert b.is_within_bounds(Position(7, 7))
    assert not b.is_within_bounds(Position(-1, 0))
    assert not b.is_within_bounds(Position(0, 8))
    assert not b.is_within_bounds(Position(8, 0))


def test_get_piece_at_returns_none_for_empty():
    b = make_board()
    assert b.get_piece_at(Position(2, 0)) is None


def test_get_piece_at_returns_piece():
    b = make_board()
    p = b.get_piece_at(Position(0, 0))
    assert p == Piece(color='w', type='R', cell=Position(0, 0))


def test_get_piece_at_out_of_bounds_returns_none():
    b = make_board()
    assert b.get_piece_at(Position(-1, -1)) is None
    assert b.get_piece_at(Position(100, 100)) is None


def test_set_piece_at_places_and_clears():
    b = make_board()
    b.set_piece_at(Position(2, 0), Piece(color='w', type='Q'))
    assert b.get_piece_at(Position(2, 0)) == Piece(color='w', type='Q', cell=Position(2, 0))
    b.set_piece_at(Position(2, 0), None)
    assert b.get_piece_at(Position(2, 0)) is None


def test_set_piece_at_out_of_bounds_is_noop():
    b = make_board()
    b.set_piece_at(Position(-1, 0), Piece(color='w', type='Q'))  # should not raise
    b.set_piece_at(Position(100, 100), Piece(color='w', type='Q'))


def test_is_empty_at():
    b = make_board()
    assert b.is_empty_at(Position(2, 0))
    assert not b.is_empty_at(Position(0, 0))


def test_to_rows_snapshot_is_independent_copy():
    b = make_board()
    rows = b.to_rows()
    rows[0][0] = 'zz'
    assert b.get_piece_at(Position(0, 0)).to_token() == 'wR'


def test_get_path_horizontal():
    b = make_board()
    path = b.get_path(Position(2, 0), Position(2, 3))
    assert path == [Position(2, 1), Position(2, 2), Position(2, 3)]


def test_get_path_vertical():
    b = make_board()
    path = b.get_path(Position(0, 0), Position(3, 0))
    assert path == [Position(1, 0), Position(2, 0), Position(3, 0)]


def test_get_path_diagonal():
    b = make_board()
    path = b.get_path(Position(2, 2), Position(5, 5))
    assert path == [Position(3, 3), Position(4, 4), Position(5, 5)]


def test_get_path_backwards_direction():
    b = make_board()
    path = b.get_path(Position(5, 5), Position(2, 2))
    assert path == [Position(4, 4), Position(3, 3), Position(2, 2)]


def test_get_path_knight_shape_returns_only_destination():
    b = make_board()
    path = b.get_path(Position(0, 0), Position(2, 1))
    assert path == [Position(2, 1)]


def test_get_path_same_square():
    b = make_board()
    path = b.get_path(Position(3, 3), Position(3, 3))
    assert path == [Position(3, 3)]


def test_custom_empty_token():
    b = ArrayBoard([['x', 'wK']], empty_token='x')
    assert b.is_empty_at(Position(0, 0))
    assert b.get_piece_at(Position(0, 1)) == Piece(color='w', type='K', cell=Position(0, 1))


def test_board_interface_is_abstract():
    with pytest.raises(TypeError):
        BoardInterface()
