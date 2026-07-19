from __future__ import annotations

from kungfu_chess.model.position import Position


class BoardMapper:
    """Translates raw pixel-based screen coordinates into board grid cells."""

    def __init__(self, cell_pixel_size: int):
        self._cell_pixel_size = cell_pixel_size

    def pixel_to_cell(self, x: int, y: int) -> Position:
        return Position(y // self._cell_pixel_size, x // self._cell_pixel_size)
