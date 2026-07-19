import pytest

from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position


def test_defaults():
    p = Piece(color='w', type='K')
    assert p.color == 'w'
    assert p.type == 'K'
    assert p.id is None
    assert p.cell is None
    assert p.state == 'idle'


def test_kind_alias():
    p = Piece(color='b', type='Q')
    assert p.kind == 'Q' == p.type


def test_parse():
    p = Piece.parse('wK')
    assert p.color == 'w'
    assert p.type == 'K'
    assert p.id is None
    assert p.cell is None


def test_parse_with_id_and_cell():
    pos = Position(1, 2)
    p = Piece.parse('bP', id='p1', cell=pos)
    assert p.id == 'p1'
    assert p.cell == pos


def test_to_token():
    p = Piece(color='w', type='N')
    assert p.to_token() == 'wN'


def test_with_state_returns_copy_preserving_identity():
    p = Piece(color='w', type='P', id='x', cell=Position(0, 0))
    moved = p.with_state('moving')
    assert moved.state == 'moving'
    assert moved.color == p.color
    assert moved.type == p.type
    assert moved.id == p.id
    assert moved.cell == p.cell
    assert p.state == 'idle'  # original untouched (frozen/immutable)


def test_equality_two_pieces_built_old_way():
    a = Piece(color='w', type='K')
    b = Piece(color='w', type='K')
    assert a == b


def test_frozen_immutable():
    p = Piece(color='w', type='K')
    with pytest.raises(Exception):
        p.color = 'b'
