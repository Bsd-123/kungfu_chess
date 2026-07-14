"""Third `BoardView` collaborator (plan section 7.2a / directory tree):
selection highlight + debug markers, explicitly decoupled from board
background rendering (`BoardRenderer`) and piece compositing
(`PieceRenderer`) -- a Phase 6 rejection tooltip, for example, only
ever needs to touch this file.

Draws the selection highlight from `InputState.selected`, which the
game loop fills in from **`controller.selected`** -- confirmed the only
live selection source (final_plan_verified.md section 0.4 / Phase 3
step 6). Never wire this to `snapshot.selected`: `Controller.click()`
tracks its own private `_selected` and never writes back to
`engine.selected`, so `snapshot.selected` is always `None` in the
current engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.ui.img import Img
from kungfu_chess.view.game_snapshot import GameSnapshot

SELECTION_COLOR = (0, 200, 0)     # BGR green, selection square outline
CURSOR_COLOR = (0, 220, 220)      # BGR yellow, live cursor dot
CLICK_COLOR = (0, 0, 220)         # BGR red, last-click ring


@dataclass(frozen=True)
class InputState:
    """Everything `OverlayRenderer` needs to draw a frame's debug/
    selection overlay -- built fresh each tick by the game loop from
    `Controller`/`MouseRouter`, never stored on the engine side."""
    selected: Optional[Position]
    cursor_pos: Optional[Tuple[int, int]]
    last_click_pos: Optional[Tuple[int, int]]


class OverlayRenderer:
    def __init__(self, cell_pixel_size: int):
        self._cell = cell_pixel_size

    def draw(self, frame: Img, snapshot: GameSnapshot,
              input_state: Optional[InputState]) -> None:
        if input_state is None:
            return

        if input_state.selected is not None:
            row, col = input_state.selected
            x1, y1 = col * self._cell, row * self._cell
            frame.draw_rect(x1, y1, x1 + self._cell - 1, y1 + self._cell - 1,
                             SELECTION_COLOR, thickness=3)

        if input_state.cursor_pos is not None:
            cx, cy = input_state.cursor_pos
            frame.draw_circle(cx, cy, 4, CURSOR_COLOR, thickness=-1)

        if input_state.last_click_pos is not None:
            clx, cly = input_state.last_click_pos
            frame.draw_circle(clx, cly, 10, CLICK_COLOR, thickness=2)
