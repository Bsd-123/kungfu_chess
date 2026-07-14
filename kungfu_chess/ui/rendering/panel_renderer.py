"""Fourth `BoardView` collaborator (plan Phase 5 step 5): draws player
names, live score, and a recent-moves log into the board's side panel.
`put_text`/`draw_rect` only (the `Img`-only constraint), and explicitly
decoupled from `BoardRenderer`/`PieceRenderer`/`OverlayRenderer` -- it
never touches piece animation state, just another draw call appended
onto the same frame each tick, so a slow panel update could never stall
the animation hot path (and in practice it's a handful of cheap
`put_text` calls, not slow at all)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from kungfu_chess.ui.img import Img

PANEL_DIVIDER_COLOR = (90, 90, 90)
TEXT_COLOR = (230, 230, 230)
DIM_TEXT_COLOR = (150, 150, 150)
WHITE_LABEL_COLOR = (240, 240, 240)
BLACK_LABEL_COLOR = (180, 180, 180)


@dataclass(frozen=True)
class PanelState:
    white_name: str = "White"
    black_name: str = "Black"
    white_score: int = 0
    black_score: int = 0
    recent_moves: List[str] = field(default_factory=list)


class PanelRenderer:
    def __init__(self, board_width_px: int, panel_width_px: int, board_height_px: int):
        self._x0 = board_width_px
        self._width = panel_width_px
        self._height = board_height_px

    def draw(self, frame: Img, panel_state: PanelState) -> None:
        frame.draw_rect(self._x0, 0, self._x0 + 2, self._height, PANEL_DIVIDER_COLOR)

        x = self._x0 + 18
        y = 34
        frame.put_text(f"{panel_state.white_name}", x, y, WHITE_LABEL_COLOR,
                        font_scale=0.65, thickness=2)
        frame.put_text(f"{panel_state.white_score}", self._x0 + self._width - 40, y,
                        WHITE_LABEL_COLOR, font_scale=0.65, thickness=2)

        y += 30
        frame.put_text(f"{panel_state.black_name}", x, y, BLACK_LABEL_COLOR,
                        font_scale=0.65, thickness=2)
        frame.put_text(f"{panel_state.black_score}", self._x0 + self._width - 40, y,
                        BLACK_LABEL_COLOR, font_scale=0.65, thickness=2)

        y += 20
        frame.draw_rect(self._x0 + 10, y, self._x0 + self._width - 10, y + 1,
                         PANEL_DIVIDER_COLOR)

        y += 28
        frame.put_text("Moves", x, y, DIM_TEXT_COLOR, font_scale=0.55, thickness=1)
        y += 22
        for move_text in panel_state.recent_moves:
            if y > self._height - 12:
                break
            frame.put_text(move_text, x, y, TEXT_COLOR, font_scale=0.5, thickness=1)
            y += 22
