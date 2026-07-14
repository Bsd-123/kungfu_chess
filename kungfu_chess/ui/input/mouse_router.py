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

Task 16 addition: `board_offset`/`board_size` let this class subtract
the board's screen-space offset before handing coordinates to
`Controller.click` -- `Controller`/`BoardMapper` are explicitly reused
unmodified (plan directive) and only ever understand board-space pixel
coordinates starting at `(0, 0)`, so now that the board no longer
starts at screen origin (side panels sit to its left, a name/score band
above it), the subtraction has to happen here, at the boundary, rather
than anywhere downstream. Clicks landing outside the board's pixel
bounds (i.e. in a side panel or the top/bottom band) are dropped rather
than forwarded -- they have no board-space meaning."""
from __future__ import annotations

from typing import Optional, Tuple

from kungfu_chess.input.controller import Controller


class MouseRouter:
    def __init__(self, controller: Controller,
                 board_offset: Tuple[int, int] = (0, 0),
                 board_size: Optional[Tuple[int, int]] = None):
        self._controller = controller
        self._offset_x, self._offset_y = board_offset
        self._board_size = board_size  # (width, height) in board-space pixels; None = unbounded
        self.cursor_pos: Optional[Tuple[int, int]] = None
        self.last_click_pos: Optional[Tuple[int, int]] = None

    def on_mouse_event(self, x: int, y: int, clicked: bool) -> None:
        self.cursor_pos = (x, y)
        if not clicked:
            return
        self.last_click_pos = (x, y)

        board_x, board_y = x - self._offset_x, y - self._offset_y
        if board_x < 0 or board_y < 0:
            return
        if self._board_size is not None:
            board_w, board_h = self._board_size
            if board_x >= board_w or board_y >= board_h:
                return
        self._controller.click(board_x, board_y)
