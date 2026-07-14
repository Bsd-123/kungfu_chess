"""Phase 3 step 1/4 (final_plan_verified.md): translates raw mouse
events into `Controller.click` calls. Deliberately backend-agnostic --
takes plain `(x, y, clicked)` rather than a `cv2` event object, so this
class has no `cv2` import at all (plan section 7.7: DI'd collaborators
never import `cv2` directly) and can be driven by a synthetic/fake
event source in headless tests exactly the same way a real
`Cv2Renderer` drives it.

Also tracks the last cursor position and last click position purely so
`OverlayRenderer` has something to draw a debug marker at -- neither of
those has any bearing on game logic.
"""
from __future__ import annotations

from typing import Optional, Tuple

from kungfu_chess.input.controller import Controller


class MouseRouter:
    def __init__(self, controller: Controller):
        self._controller = controller
        self.cursor_pos: Optional[Tuple[int, int]] = None
        self.last_click_pos: Optional[Tuple[int, int]] = None

    def on_mouse_event(self, x: int, y: int, clicked: bool) -> None:
        self.cursor_pos = (x, y)
        if clicked:
            self.last_click_pos = (x, y)
            self._controller.click(x, y)
