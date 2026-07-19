"""Centralized UI theme config. `UITheme` bundles per-collaborator
dataclasses (colors, sizes, durations) into one injectable object; every
renderer defaults to `DEFAULT_THEME` when none is passed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

Color = Tuple[int, ...]


@dataclass(frozen=True)
class BoardTheme:
    panel_background_color: Color = (40, 40, 40, 255)
    coord_margin_bg: Color = (60, 60, 60, 255)
    coord_text_color: Color = (230, 230, 230)
    coord_margin_px: int = 28
    file_letters: str = "abcdefgh"
    # Coordinate-label offsets from cell center / margin edges.
    coord_font_scale: float = 0.5
    coord_label_col_dx: int = -6
    coord_label_top_dy: int = -9
    coord_label_bottom_dy: int = -9
    coord_label_row_dy: int = 6
    coord_label_row_left_x: int = 10
    coord_label_row_right_dx: int = -20


@dataclass(frozen=True)
class OverlayTheme:
    selection_color: Color = (0, 200, 0)          # BGR green, selection outline
    move_highlight_color: Color = (0, 255, 255)   # BGR yellow, legal-destination fill
    move_highlight_base_alpha: int = 128
    move_highlight_pulse_amplitude: int = 40
    move_highlight_pulse_period_ms: float = 1400.0
    selection_thickness: int = 3  # selection-rectangle outline width


@dataclass(frozen=True)
class PieceAnimationTheme:
    jump_hop_height_px: int = 18
    fade_duration_ms: float = 220.0
    correction_duration_ms: float = 180.0
    cooldown_overlay_color: Color = (0, 140, 255, 150)  # BGRA, orange
    cooldown_wheel_radius_ratio: float = 0.46


@dataclass(frozen=True)
class PanelTheme:
    panel_bg_color: Color = (40, 40, 40)
    divider_color: Color = (90, 90, 90)
    name_box_color: Color = (70, 70, 70)
    text_color: Color = (230, 230, 230)
    dim_text_color: Color = (160, 160, 160)
    header_color: Color = (200, 200, 200)
    row_height: int = 22
    name_box_height: int = 36
    name_box_margin: int = 12
    move_col_offset_px: int = 78          # "Move" column x, from name box's left edge
    header_offset_px: int = 26            # header y, from name box's bottom edge
    divider_gap_px: int = 6               # divider y, from header row
    divider_thickness_px: int = 1
    row_start_offset_px: int = 30         # first move row y, from header row
    name_font_scale: float = 0.6
    name_thickness: int = 2
    header_font_scale: float = 0.5
    header_thickness: int = 1
    row_font_scale: float = 0.5
    row_thickness: int = 1
    time_font_scale: float = 0.42
    time_thickness: int = 1
    center_band_font_scale: float = 0.55
    center_band_thickness: int = 1


@dataclass(frozen=True)
class ToastTheme:
    box_width: int = 320
    box_height: int = 110
    box_bg_color: Color = (20, 20, 20, 225)     # BGRA, translucent dark background
    box_border_color: Color = (60, 220, 255)    # BGR, amber
    text_color: Color = (245, 245, 245)
    drop_distance_px: int = 140
    duration_ms: float = 900.0
    # subtitle_gap_px pulls the title up and pushes the subtitle down
    # symmetrically from the box's vertical center.
    title_font_scale: float = 1.0
    subtitle_font_scale: float = 0.7
    text_thickness: int = 2
    subtitle_gap_px: int = 8


@dataclass(frozen=True)
class WindowTheme:
    """Window/input config, shared by `cv2_renderer.py` and `img.py`'s
    `window_name` default to keep them in sync."""
    window_name: str = "Kung Fu Chess"
    quit_keys: Tuple[int, ...] = (27, ord('q'))  # Esc, q
    wait_ms: int = 1


@dataclass(frozen=True)
class LayoutTheme:
    left_panel_width_px: int = 190
    right_panel_width_px: int = 190
    # Target window height; top/bottom bands split the leftover space
    # after the board image height (see ui/layout.py).
    target_total_height_px: int = 900
    min_band_height_px: int = 20


@dataclass(frozen=True)
class UITheme:
    """Top-level bundle; grouped by collaborator so each renderer only
    depends on its own slice."""
    board: BoardTheme = field(default_factory=BoardTheme)
    overlay: OverlayTheme = field(default_factory=OverlayTheme)
    piece_animation: PieceAnimationTheme = field(default_factory=PieceAnimationTheme)
    panel: PanelTheme = field(default_factory=PanelTheme)
    toast: ToastTheme = field(default_factory=ToastTheme)
    layout: LayoutTheme = field(default_factory=LayoutTheme)
    window: WindowTheme = field(default_factory=WindowTheme)


DEFAULT_THEME = UITheme()
