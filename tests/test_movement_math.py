import pytest

from kungfu_chess.engine.movement_math import squares_traveled
from kungfu_chess.model.position import Position


@pytest.mark.parametrize("src,dst,expected", [
    (Position(0, 0), Position(0, 3), 3),
    (Position(0, 0), Position(3, 0), 3),
    (Position(0, 0), Position(3, 3), 3),
    (Position(0, 0), Position(2, 1), 2),  # knight-shape: chebyshev, not euclidean
    (Position(0, 0), Position(0, 0), 1),  # zero-distance floors to 1
    (Position(5, 5), Position(3, 2), 3),
])
def test_squares_traveled(src, dst, expected):
    assert squares_traveled(src, dst) == expected
