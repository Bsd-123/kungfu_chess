"""Pure drawing helper for the post-move cooldown "wheel" overlay.
Stateless: `Img` in, `Img` mutated in place via `draw_on`, no
dependency on `PieceRenderer`'s own tracking state."""
from __future__ import annotations

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.theme import PieceAnimationTheme


def draw_cooldown_overlay(frame: Img, cell_pixel_size: int, x: int, y: int,
                           progress: float, theme: PieceAnimationTheme) -> None:
    """Draws the remaining-cooldown wedge over a piece at `(x, y)`.
    `progress` goes 0.0 (just settled) -> 1.0 (finished); the wedge shows
    `1.0 - progress`, sweeping away clockwise from 12 o'clock. Painted on
    a transparent tile and alpha-composited via `Img.draw_on`, since
    plain cv2 drawing would overwrite pixels instead of blending."""
    remaining = 1.0 - progress
    if remaining <= 0.0:
        return

    tile = Img.new(cell_pixel_size, cell_pixel_size, channels=4, color=(0, 0, 0, 0))
    cx, cy = cell_pixel_size // 2, cell_pixel_size // 2
    radius = int(cell_pixel_size * theme.cooldown_wheel_radius_ratio)
    end_angle = -90 + 360 * remaining
    tile.draw_ellipse(cx, cy, (radius, radius), theme.cooldown_overlay_color,
                       start_angle=-90, end_angle=end_angle)
    frame.draw_on(tile, x, y)
