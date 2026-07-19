"""Translates raw mouse events into `Controller.click` calls. Backend-
agnostic: takes plain `(x, y, clicked)`, no `cv2` dependency. Subtracts
`board_offset` to convert screen-space to board-space coordinates before
forwarding; clicks outside `board_size` bounds are dropped."""
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
        # Unused by any current renderer; kept for a future debug overlay.
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
