"""Concrete `cv2` window + event-loop backend (plan Phase 2/3 plumbing,
plumbing note 1: "From Phase 2 on, drive cv2.imshow + cv2.waitKey(1)
directly" instead of the blocking one-off `Img.show()` used in Phase 1).

Phase 3 plumbing note 6 (window-resize vs. mouse-coordinate scaling):
this class has used `cv2.WINDOW_AUTOSIZE` since Phase 2, which is the
plan's own documented fallback -- the window can't be resized by the
user at all, so the image and the window are always pixel-for-pixel
identical and mouse coordinates from `cv2.setMouseCallback` need zero
translation before reaching `Controller.click`. That resolves Phase 3
step 2/3 with no separate scaling layer required.
"""
from __future__ import annotations

import cv2

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.renderer import MouseHandler, Renderer

QUIT_KEYS = (27, ord('q'))  # Esc, q


class Cv2Renderer(Renderer):
    def __init__(self, window_name: str = "Kung Fu Chess", wait_ms: int = 1):
        self._window_name = window_name
        self._wait_ms = wait_ms
        cv2.namedWindow(self._window_name, cv2.WINDOW_AUTOSIZE)

    def draw_frame(self, frame: Img) -> None:
        cv2.imshow(self._window_name, frame.array)

    def poll_events(self) -> bool:
        key = cv2.waitKey(self._wait_ms) & 0xFF
        if key in QUIT_KEYS:
            return False

        # Detect the window's close ('x') button -- getWindowProperty
        # drops below 1 once the user has closed it, even though no key
        # was pressed.
        try:
            visible = cv2.getWindowProperty(self._window_name,
                                             cv2.WND_PROP_VISIBLE)
        except cv2.error:
            return False
        return visible >= 1

    def register_mouse_handler(self, handler: MouseHandler) -> None:
        """Translates cv2's own event vocabulary (EVENT_LBUTTONDOWN,
        EVENT_MOUSEMOVE, ...) down to the backend-agnostic
        `(x, y, clicked)` shape `MouseRouter` expects, so no other UI
        collaborator needs to know `cv2`'s event codes exist."""
        def _on_cv2_mouse(event, x, y, flags, param) -> None:
            handler(x, y, event == cv2.EVENT_LBUTTONDOWN)

        cv2.setMouseCallback(self._window_name, _on_cv2_mouse)

    def close(self) -> None:
        """Best-effort teardown. On Windows, closing the window via its
        'x' button destroys the underlying OS window immediately --
        `poll_events` then correctly reports "stop", but by the time we
        get here `cv2.destroyWindow` has nothing left to destroy and
        raises a `cv2.error` ("NULL window") for a window that's already
        gone. That's not a real failure from this method's point of
        view (the goal -- no window left open -- is already true), so
        it's swallowed rather than propagated."""
        try:
            cv2.destroyWindow(self._window_name)
        except cv2.error:
            pass
