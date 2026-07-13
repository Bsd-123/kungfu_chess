from __future__ import annotations

from kungfu_chess.model.position import Position


class BoardMapper:
    """Coordinate Adapter (Rule 4): the single place that translates raw,
    pixel-based screen coordinates into board grid cells. No other
    component performs this conversion -- callers ask the mapper instead
    of doing the arithmetic themselves, so the pixel/grid relationship
    can change (e.g. non-square cells, a scrolled/zoomed viewport) without
    touching command parsing or game logic."""

    def __init__(self, cell_pixel_size: int):
        self._cell_pixel_size = cell_pixel_size

    def pixel_to_cell(self, x: int, y: int) -> Position:
        return Position(y // self._cell_pixel_size, x // self._cell_pixel_size)
