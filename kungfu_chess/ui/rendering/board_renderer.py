"""Phase 1 (final_plan_verified.md Phase 1 step 1): background-only
renderer. Owns the pristine board-background template -- read once,
forced to BGRA immediately (plumbing note 3) -- and hands out a fresh
`.copy()` (plumbing note 5) every frame so nothing downstream ever
mutates the original.

Reworked for real-asset support: the raw checkerboard image this class
reads (`background_path`) is expected to be a *plain* NxM checkerboard
with no margin or coordinate labels baked in -- true for both
`generate_placeholder_assets.generate_board`'s placeholder art AND a
real external board image someone drops in (which will never happen to
carry this app's specific label styling/margin). This class stretches
whatever it's given to exactly `cell_pixel_size * cols x cell_pixel_size
* rows` (guaranteeing pieces line up on exact cell boundaries
regardless of the source image's native resolution -- a real asset's
photographed/exported board is very unlikely to be a clean multiple of
`cell_pixel_size` pixels per square) and draws the file/rank coordinate
-label margin itself, uniformly, around whatever checkerboard art it's
given.

This replaces an earlier design where `generate_placeholder_assets`
baked its own margin+labels directly into `board.png`, and `ui/app.py`
had to duplicate (or, briefly, re-measure) that same margin to keep
piece placement in sync -- fragile the moment a *different* board image
(a real external asset, or a differently-sized generated one) shows up.
Now there is nothing to measure or duplicate: `COORD_MARGIN_PX` is
authored in exactly one place, and every board image gets it applied
identically."""
from __future__ import annotations

from kungfu_chess.ui.img import Img

PANEL_BACKGROUND_COLOR = (40, 40, 40, 255)
COORD_MARGIN_BG = (60, 60, 60, 255)
COORD_TEXT_COLOR = (230, 230, 230)
COORD_MARGIN_PX = 28
FILE_LETTERS = "abcdefgh"


class BoardRenderer:
    def __init__(self, background_path: str, cell_pixel_size: int,
                 cols: int, rows: int,
                 board_offset_x: int = 0, board_offset_y: int = 0,
                 total_width: int = None, total_height: int = None):
        board_w, board_h = cell_pixel_size * cols, cell_pixel_size * rows
        # Stretch (not letterbox) to exactly board_w x board_h -- a real
        # asset's own aspect ratio is very unlikely to be a perfect 1:1
        # square already, and we need cell boundaries to land on exact
        # multiples of cell_pixel_size, not "as close as aspect-
        # preserving resize allows".
        checkerboard = Img().read(background_path, size=(board_w, board_h))
        checkerboard.to_bgra()

        labeled = self._add_coord_margin(checkerboard, cell_pixel_size, cols, rows)
        self.image_width = labeled.width
        self.image_height = labeled.height

        width = total_width if total_width is not None else labeled.width
        height = total_height if total_height is not None else labeled.height

        if width == labeled.width and height == labeled.height:
            # No surrounding panel space requested -- keep the template
            # exactly the labeled checkerboard, unchanged from Phase 1.
            self._template = labeled
        else:
            template = Img.new(width, height, channels=4, color=PANEL_BACKGROUND_COLOR)
            template.draw_on(labeled, board_offset_x, board_offset_y)
            self._template = template

    @staticmethod
    def _add_coord_margin(checkerboard: Img, cell: int, cols: int, rows: int) -> Img:
        board_w, board_h = checkerboard.width, checkerboard.height
        total_w = board_w + 2 * COORD_MARGIN_PX
        total_h = board_h + 2 * COORD_MARGIN_PX

        canvas = Img.new(total_w, total_h, channels=4, color=COORD_MARGIN_BG)
        canvas.draw_on(checkerboard, COORD_MARGIN_PX, COORD_MARGIN_PX)

        font_scale = 0.5
        for col in range(cols):
            label = FILE_LETTERS[col]
            x = COORD_MARGIN_PX + col * cell + cell // 2 - 6
            canvas.put_text(label, x, COORD_MARGIN_PX - 9, COORD_TEXT_COLOR,
                             font_scale=font_scale, thickness=1)
            canvas.put_text(label, x, total_h - 9, COORD_TEXT_COLOR,
                             font_scale=font_scale, thickness=1)
        for row in range(rows):
            label = str(rows - row)
            y = COORD_MARGIN_PX + row * cell + cell // 2 + 6
            canvas.put_text(label, 10, y, COORD_TEXT_COLOR,
                             font_scale=font_scale, thickness=1)
            canvas.put_text(label, total_w - 20, y, COORD_TEXT_COLOR,
                             font_scale=font_scale, thickness=1)
        return canvas

    def fresh_frame(self) -> Img:
        return self._template.copy()
