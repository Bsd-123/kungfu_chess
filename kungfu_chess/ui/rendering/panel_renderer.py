"""Fourth `BoardView` collaborator (plan Phase 5 step 5), reworked for
task 16 to match the reference mockup: a Black panel on the left and a
White panel on the right, each with its own name-label box and a
Time|Move table of that color's recent moves, plus centered
"Name: X" / "Score: N" text above the board (Black -- row 0 is black's
back rank, so black is visually "on top") and below it (White).

`put_text`/`draw_rect`/`text_size` only (the `Img`-only constraint),
and explicitly decoupled from `BoardRenderer`/`PieceRenderer`/
`OverlayRenderer` -- it never touches piece animation state, just
another draw call appended onto the same frame each tick."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from kungfu_chess.ui.events.observers.moves_log_observer import LoggedMove, format_time_ms
from kungfu_chess.ui.img import Img

PANEL_BG_COLOR = (40, 40, 40)
DIVIDER_COLOR = (90, 90, 90)
NAME_BOX_COLOR = (70, 70, 70)
TEXT_COLOR = (230, 230, 230)
DIM_TEXT_COLOR = (160, 160, 160)
HEADER_COLOR = (200, 200, 200)

ROW_HEIGHT = 22
NAME_BOX_HEIGHT = 36
NAME_BOX_MARGIN = 12


@dataclass(frozen=True)
class PanelState:
    white_name: str = "White"
    black_name: str = "Black"
    white_score: int = 0
    black_score: int = 0
    white_moves: List[LoggedMove] = field(default_factory=list)
    black_moves: List[LoggedMove] = field(default_factory=list)


class PanelRenderer:
    def __init__(self, left_panel_x0: int, left_panel_width: int,
                 right_panel_x0: int, right_panel_width: int,
                 panel_height: int, board_x0: int, board_width: int,
                 top_band_y0: int, top_band_height: int,
                 bottom_band_y0: int, bottom_band_height: int):
        self._left_x0 = left_panel_x0
        self._left_w = left_panel_width
        self._right_x0 = right_panel_x0
        self._right_w = right_panel_width
        self._panel_h = panel_height
        self._board_cx = board_x0 + board_width // 2
        self._top_y0 = top_band_y0
        self._top_h = top_band_height
        self._bottom_y0 = bottom_band_y0
        self._bottom_h = bottom_band_height

    def draw(self, frame: Img, panel_state: PanelState) -> None:
        self._draw_side_panel(frame, self._left_x0, self._left_w,
                               panel_state.black_name, panel_state.black_moves)
        self._draw_side_panel(frame, self._right_x0, self._right_w,
                               panel_state.white_name, panel_state.white_moves)
        self._draw_center_band(frame, self._top_y0, self._top_h,
                                panel_state.black_name, panel_state.black_score)
        self._draw_center_band(frame, self._bottom_y0, self._bottom_h,
                                panel_state.white_name, panel_state.white_score)

    def _draw_side_panel(self, frame: Img, x0: int, width: int,
                          name: str, moves: List[LoggedMove]) -> None:
        frame.draw_rect(x0, 0, x0 + width, self._panel_h, PANEL_BG_COLOR)

        box_x1, box_y1 = x0 + NAME_BOX_MARGIN, NAME_BOX_MARGIN
        box_x2, box_y2 = x0 + width - NAME_BOX_MARGIN, NAME_BOX_MARGIN + NAME_BOX_HEIGHT
        frame.draw_rect(box_x1, box_y1, box_x2, box_y2, NAME_BOX_COLOR)
        name_w, name_h = frame.text_size(name, font_scale=0.6, thickness=2)
        frame.put_text(name, (box_x1 + box_x2) // 2 - name_w // 2,
                        (box_y1 + box_y2) // 2 + name_h // 2, TEXT_COLOR,
                        font_scale=0.6, thickness=2)

        move_col_x = box_x1 + 78
        header_y = box_y2 + 26
        frame.put_text("Time", box_x1 + 4, header_y, HEADER_COLOR,
                        font_scale=0.5, thickness=1)
        frame.put_text("Move", move_col_x, header_y, HEADER_COLOR,
                        font_scale=0.5, thickness=1)
        frame.draw_rect(box_x1, header_y + 6, box_x2, header_y + 7, DIVIDER_COLOR)

        y = header_y + 30
        max_rows = max(0, (self._panel_h - y - 10) // ROW_HEIGHT)
        visible = moves[-max_rows:] if max_rows > 0 else []
        for move in visible:
            frame.put_text(format_time_ms(move.time_ms), box_x1 + 4, y,
                            DIM_TEXT_COLOR, font_scale=0.42, thickness=1)
            frame.put_text(move.text, move_col_x, y, TEXT_COLOR,
                            font_scale=0.5, thickness=1)
            y += ROW_HEIGHT

    def _draw_center_band(self, frame: Img, y0: int, height: int,
                           name: str, score: int) -> None:
        """A single centered line ("Name: X    Score: N"), sized to fit
        even a narrow band comfortably. Two stacked lines (name above
        score) don't fit once the band shrinks to make room for a fixed
        overall window height (`TARGET_TOTAL_HEIGHT_PX`) -- one line,
        vertically centered by its own measured text height, stays
        readable at any band height down to `MIN_BAND_HEIGHT_PX`."""
        text = f"Name: {name}    Score: {score}"
        text_w, text_h = frame.text_size(text, font_scale=0.55, thickness=1)
        text_y = y0 + height // 2 + text_h // 2
        frame.put_text(text, self._board_cx - text_w // 2, text_y,
                        TEXT_COLOR, font_scale=0.55, thickness=1)
