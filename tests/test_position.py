from kungfu_chess.model.position import Position


def test_fields():
    p = Position(1, 2)
    assert p.row == 1
    assert p.col == 2


def test_indexable_and_iterable():
    p = Position(3, 4)
    assert p[0] == 3
    assert p[1] == 4
    row, col = p
    assert (row, col) == (3, 4)


def test_equality_and_hash():
    assert Position(1, 1) == Position(1, 1)
    assert Position(1, 1) != Position(1, 2)
    assert hash(Position(1, 1)) == hash((1, 1))
    s = {Position(0, 0), Position(0, 0), Position(1, 1)}
    assert len(s) == 2


def test_repr_readable():
    assert "1" in repr(Position(1, 2)) and "2" in repr(Position(1, 2))
