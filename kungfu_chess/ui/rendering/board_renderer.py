"""Phase 1 (final_plan_verified.md Phase 1 step 1): background-only
renderer. Owns the pristine board-background template -- read once,
forced to BGRA immediately (plumbing note 3) -- and hands out a fresh
`.copy()` (plumbing note 5) every frame so nothing downstream ever
mutates the original.

Reworked for the reference-mockup layout (task 16): the checkerboard
PNG (`generate_placeholder_assets.generate_board`, itself already
carrying a baked-in file/rank coordinate-label margin) gets pasted onto
a wider/taller canvas at `(board_offset_x, board_offset_y)`, leaving
room around it for two side panels (Black/White) and a top/bottom
name+score band -- all painted by `PanelRenderer` on top of this same
frame, later in `BoardView.render`. This class only owns the *board*
image and the flat panel-colored backdrop behind it; it knows nothing
about panel content."""
from __future__ import annotations

from kungfu_chess.ui.img import Img

PANEL_BACKGROUND_COLOR = (40, 40, 40, 255)


class BoardRenderer:
    def __init__(self, background_path: str,
                 board_offset_x: int = 0, board_offset_y: int = 0,
                 total_width: int = None, total_height: int = None):
        checkerboard = Img().read(background_path)
        checkerboard.to_bgra()

        width = total_width if total_width is not None else checkerboard.width
        height = total_height if total_height is not None else checkerboard.height

        if width == checkerboard.width and height == checkerboard.height:
            # No surrounding panel space requested -- keep the template
            # exactly the plain checkerboard, unchanged from Phase 1.
            self._template = checkerboard
        else:
            template = Img.new(width, height, channels=4, color=PANEL_BACKGROUND_COLOR)
            template.draw_on(checkerboard, board_offset_x, board_offset_y)
            self._template = template

    def fresh_frame(self) -> Img:
        return self._template.copy()
