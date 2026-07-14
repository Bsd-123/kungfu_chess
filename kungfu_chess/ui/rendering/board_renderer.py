"""Phase 1 (final_plan_verified.md Phase 1 step 1): background-only
renderer. Owns the pristine board-background template -- read once,
forced to BGRA immediately (plumbing note 3) -- and hands out a fresh
`.copy()` (plumbing note 5) every frame so nothing downstream ever
mutates the original.

Phase 5 addition: optionally composites the (unchanged) checkerboard
onto a wider canvas with a solid sidebar region for `PanelRenderer`.
`generate_placeholder_assets.py`'s `board.png` stays exactly the plain
8x8 checkerboard it always was -- the panel-width extension happens
here, at template-build time, once, not baked into the asset itself."""
from __future__ import annotations

from kungfu_chess.ui.img import Img

PANEL_BACKGROUND_COLOR = (40, 40, 40, 255)


class BoardRenderer:
    def __init__(self, background_path: str, panel_width_px: int = 0):
        checkerboard = Img().read(background_path)
        checkerboard.to_bgra()

        if panel_width_px > 0:
            total_width = checkerboard.width + panel_width_px
            template = Img.new(total_width, checkerboard.height, channels=4,
                                color=PANEL_BACKGROUND_COLOR)
            template.draw_on(checkerboard, 0, 0)
            self._template = template
        else:
            self._template = checkerboard

    def fresh_frame(self) -> Img:
        return self._template.copy()
