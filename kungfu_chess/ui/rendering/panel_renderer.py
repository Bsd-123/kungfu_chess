"""Draws side panels (Black left, White right) with a name box and a
Time|Move table, plus centered "Name: X  Score: N" bands above/below
the board."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from kungfu_chess.ui.events.observers.moves_log_observer import LoggedMove, format_time_ms
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.theme import DEFAULT_THEME, PanelTheme


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
                 bottom_band_y0: int, bottom_band_height: int,
                 theme: PanelTheme = DEFAULT_THEME.panel):
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
        self._theme = theme

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
        theme = self._theme
        frame.draw_rect(x0, 0, x0 + width, self._panel_h, theme.panel_bg_color)

        box_x1, box_y1 = x0 + theme.name_box_margin, theme.name_box_margin
        box_x2 = x0 + width - theme.name_box_margin
        box_y2 = theme.name_box_margin + theme.name_box_height
        frame.draw_rect(box_x1, box_y1, box_x2, box_y2, theme.name_box_color)
        name_w, name_h = frame.text_size(name, font_scale=theme.name_font_scale,
                                          thickness=theme.name_thickness)
        frame.put_text(name, (box_x1 + box_x2) // 2 - name_w // 2,
                        (box_y1 + box_y2) // 2 + name_h // 2, theme.text_color,
                        font_scale=theme.name_font_scale, thickness=theme.name_thickness)

        move_col_x = box_x1 + theme.move_col_offset_px
        header_y = box_y2 + theme.header_offset_px
        frame.put_text("Time", box_x1 + 4, header_y, theme.header_color,
                        font_scale=theme.header_font_scale, thickness=theme.header_thickness)
        frame.put_text("Move", move_col_x, header_y, theme.header_color,
                        font_scale=theme.header_font_scale, thickness=theme.header_thickness)
        frame.draw_rect(box_x1, header_y + theme.divider_gap_px, box_x2,
                         header_y + theme.divider_gap_px + theme.divider_thickness_px,
                         theme.divider_color)

        y = header_y + theme.row_start_offset_px
        max_rows = max(0, (self._panel_h - y - 10) // theme.row_height)
        visible = moves[-max_rows:] if max_rows > 0 else []
        for move in visible:
            frame.put_text(format_time_ms(move.time_ms), box_x1 + 4, y,
                            theme.dim_text_color, font_scale=theme.time_font_scale,
                            thickness=theme.time_thickness)
            frame.put_text(move.text, move_col_x, y, theme.text_color,
                            font_scale=theme.row_font_scale, thickness=theme.row_thickness)
            y += theme.row_height

    def _draw_center_band(self, frame: Img, y0: int, height: int,
                           name: str, score: int) -> None:
        """Centers the line vertically using its own measured text height."""
        theme = self._theme
        text = f"Name: {name}    Score: {score}"
        text_w, text_h = frame.text_size(text, font_scale=theme.center_band_font_scale,
                                          thickness=theme.center_band_thickness)
        text_y = y0 + height // 2 + text_h // 2
        frame.put_text(text, self._board_cx - text_w // 2, text_y,
                        theme.text_color, font_scale=theme.center_band_font_scale,
                        thickness=theme.center_band_thickness)
