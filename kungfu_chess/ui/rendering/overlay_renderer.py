"""Third `BoardView` collaborator (plan section 7.2a / directory tree):
selection highlight, explicitly decoupled from board background
rendering (`BoardRenderer`) and piece compositing (`PieceRenderer`) --
a Phase 6 rejection tooltip, for example, only ever needs to touch
this file.

Draws the selection highlight from `InputState.selected`, which the
game loop fills in from **`controller.selected`** -- confirmed the only
live selection source (final_plan_verified.md section 0.4 / Phase 3
step 6). Never wire this to `snapshot.selected`: `Controller.click()`
tracks its own private `_selected` and never writes back to
`engine.selected`, so `snapshot.selected` is always `None` in the
current engine.

`InputState` still carries `cursor_pos`/`last_click_pos` (`MouseRouter`
tracks them regardless), but this renderer no longer draws them --
the yellow live-cursor dot and red last-click ring were debug markers
from Phase 3 plumbing, not part of the actual game UI, and are gone
per request. Left the fields in place rather than ripping them out of
`MouseRouter`/`InputState` too, since some future debug overlay could
still want them without re-threading the mouse-tracking plumbing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.ui.img import Img
from kungfu_chess.view.game_snapshot import GameSnapshot

SELECTION_COLOR = (0, 200, 0)     # BGR green, selection square outline


@dataclass(frozen=True)
class InputState:
    """Everything `OverlayRenderer` needs to draw a frame's selection
    overlay -- built fresh each tick by the game loop from
    `Controller`/`MouseRouter`, never stored on the engine side."""
    selected: Optional[Position]
    cursor_pos: Optional[Tuple[int, int]]
    last_click_pos: Optional[Tuple[int, int]]


class OverlayRenderer:
    def __init__(self, cell_pixel_size: int, offset: Tuple[int, int] = (0, 0)):
        """`offset` (task 16): board-space screen offset applied to the
        selection highlight, which is computed from a board `Position`
        (`InputState.selected`, board-space)."""
        self._cell = cell_pixel_size
        self._offset = offset

    def draw(self, frame: Img, snapshot: GameSnapshot,
              input_state: Optional[InputState]) -> None:
        if input_state is None or input_state.selected is None:
            return

        row, col = input_state.selected
        off_x, off_y = self._offset
        x1, y1 = off_x + col * self._cell, off_y + row * self._cell
        frame.draw_rect(x1, y1, x1 + self._cell - 1, y1 + self._cell - 1,
                         SELECTION_COLOR, thickness=3)
