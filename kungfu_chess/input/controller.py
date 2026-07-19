from __future__ import annotations
from typing import Optional

from kungfu_chess.model.position import Position
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.engine.game_engine import GameEngine


class Controller:
    """Click interpretation layer: pixel-to-cell translation plus selected-cell state.
    Does not decide legality, only forwards intents to GameEngine."""

    def __init__(self, engine: GameEngine, cell_pixel_size: int):
        self._engine = engine
        self._mapper = BoardMapper(cell_pixel_size)
        self._selected: Optional[Position] = None

    @property
    def selected(self) -> Optional[Position]:
        return self._selected

    def click(self, x: int, y: int) -> None:
        pos = self._mapper.pixel_to_cell(x, y)

        if not self._engine.board.is_within_bounds(pos):
            # Outside-board click cancels any current selection.
            self._selected = None
            return

        cell = self._engine.board.get_piece_at(pos)

        if self._selected is None:
            if cell is not None:
                self._selected = pos
            return

        sel = self._selected
        sel_piece = self._engine.board.get_piece_at(sel)
        if sel_piece is None:
            self._selected = None
            return

        if pos == sel:
            self._engine.request_jump(sel)
        elif cell is not None and cell.color == sel_piece.color:
            self._selected = pos
            return
        else:
            self._engine.request_move(sel, pos)

        self._selected = None
