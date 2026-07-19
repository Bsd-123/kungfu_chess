"""`cv2.imshow`/`cv2.waitKey`-based window backend. Mouse coords are
passed through unrescaled -- Win32 HighGUI already maps them back to
the original image space on resize -- only clamped to frame bounds."""
from __future__ import annotations

from typing import Optional, Tuple

import cv2

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.renderer import MouseHandler, Renderer
from kungfu_chess.ui.theme import DEFAULT_THEME, WindowTheme

QUIT_KEYS = DEFAULT_THEME.window.quit_keys


class Cv2Renderer(Renderer):
    def __init__(self, window_name: Optional[str] = None, wait_ms: Optional[int] = None,
                 theme: WindowTheme = DEFAULT_THEME.window):
        self._theme = theme
        self._window_name = window_name if window_name is not None else theme.window_name
        self._wait_ms = wait_ms if wait_ms is not None else theme.wait_ms
        self._native_w: Optional[int] = None
        self._native_h: Optional[int] = None
        cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)

    def draw_frame(self, frame: Img) -> None:
        self._native_h, self._native_w = frame.array.shape[:2]
        cv2.imshow(self._window_name, frame.array)

    def poll_events(self) -> bool:
        key = cv2.waitKey(self._wait_ms) & 0xFF
        if key in self._theme.quit_keys:
            return False

        # getWindowProperty drops below 1 once the window's 'x' is clicked.
        try:
            visible = cv2.getWindowProperty(self._window_name,
                                             cv2.WND_PROP_VISIBLE)
        except cv2.error:
            return False
        return visible >= 1

    def register_mouse_handler(self, handler: MouseHandler) -> None:
        """Translates cv2 mouse events into the backend-agnostic
        `(x, y, clicked)` shape `MouseRouter` expects."""
        def _on_cv2_mouse(event, x, y, flags, param) -> None:
            x, y = self._clamp_to_frame(x, y)
            handler(x, y, event == cv2.EVENT_LBUTTONDOWN)

        cv2.setMouseCallback(self._window_name, _on_cv2_mouse)

    def _clamp_to_frame(self, x: int, y: int) -> Tuple[int, int]:
        if self._native_w is None or self._native_h is None:
            return x, y
        return (max(0, min(self._native_w - 1, x)),
                max(0, min(self._native_h - 1, y)))

    def close(self) -> None:
        """Swallows `cv2.error` if the window was already closed via 'x'."""
        try:
            cv2.destroyWindow(self._window_name)
        except cv2.error:
            pass
