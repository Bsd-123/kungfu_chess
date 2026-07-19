"""Screen-space geometry for the board layout, computed once from
`GameConfig`/`UITheme.layout` and shared by every renderer that needs it.
Plain-value holder, not itself a renderer.

`BOARD_COLS`/`BOARD_ROWS` mirror the engine's board dimensions but are
hardcoded here since `Layout` is built before any `GameEngine` exists."""
from __future__ import annotations

from kungfu_chess.config import GameConfig
from kungfu_chess.ui.theme import DEFAULT_THEME, UITheme

BOARD_COLS = 8
BOARD_ROWS = 8


class Layout:
    def __init__(self, config: GameConfig, theme: UITheme = DEFAULT_THEME):
        layout_theme = theme.layout
        coord_margin_px = theme.board.coord_margin_px

        self.board_w = config.cell_pixel_size * BOARD_COLS
        self.board_h = config.cell_pixel_size * BOARD_ROWS
        board_image_w = self.board_w + 2 * coord_margin_px
        board_image_h = self.board_h + 2 * coord_margin_px

        leftover = layout_theme.target_total_height_px - board_image_h
        top_band_height = max(layout_theme.min_band_height_px, leftover // 2)
        bottom_band_height = max(layout_theme.min_band_height_px, leftover - top_band_height)
        self.top_band_height = top_band_height
        self.bottom_band_height = bottom_band_height

        self.board_offset_x = layout_theme.left_panel_width_px
        self.board_offset_y = top_band_height

        # Where board cell (0, 0) starts on screen.
        self.piece_offset = (self.board_offset_x + coord_margin_px,
                              self.board_offset_y + coord_margin_px)

        self.total_width = layout_theme.left_panel_width_px + board_image_w + layout_theme.right_panel_width_px
        self.total_height = top_band_height + board_image_h + bottom_band_height

        self.right_panel_x0 = self.board_offset_x + board_image_w
        self.bottom_band_y0 = self.board_offset_y + board_image_h
        self.board_image_w = board_image_w
        self.board_image_h = board_image_h
        self.left_panel_width_px = layout_theme.left_panel_width_px
        self.right_panel_width_px = layout_theme.right_panel_width_px
