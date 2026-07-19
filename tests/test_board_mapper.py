from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.model.position import Position


def test_pixel_to_cell_basic():
    mapper = BoardMapper(100)
    assert mapper.pixel_to_cell(0, 0) == Position(0, 0)
    assert mapper.pixel_to_cell(150, 250) == Position(2, 1)


def test_pixel_to_cell_different_cell_size():
    mapper = BoardMapper(50)
    assert mapper.pixel_to_cell(120, 60) == Position(1, 2)
