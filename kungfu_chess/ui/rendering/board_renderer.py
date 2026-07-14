"""Phase 1 (final_plan_verified.md Phase 1 step 1): background-only
renderer. Owns the pristine board-background template -- read once,
forced to BGRA immediately (plumbing note 3) -- and hands out a fresh
`.copy()` (plumbing note 5) every frame so nothing downstream ever
mutates the original."""
from __future__ import annotations

from kungfu_chess.ui.img import Img


class BoardRenderer:
    def __init__(self, background_path: str):
        self._template = Img().read(background_path)
        self._template.to_bgra()

    def fresh_frame(self) -> Img:
        return self._template.copy()
