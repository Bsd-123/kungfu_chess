"""Concrete `cv2` window + event-loop backend (plan Phase 2/3 plumbing,
plumbing note 1: "From Phase 2 on, drive cv2.imshow + cv2.waitKey(1)
directly" instead of the blocking one-off `Img.show()` used in Phase 1).

Phase 3 plumbing note 6 originally used `cv2.WINDOW_AUTOSIZE` specifically
to dodge window-resize/mouse-coordinate scaling. Reworked to allow
resizing (`cv2.WINDOW_NORMAL`) -- but *without* any manual coordinate
rescaling. First attempt at this added a manual rescale via
`cv2.getWindowImageRect` (native size / displayed size), reasoning that
`cv2.imshow` stretches the image to fill a resized window so raw mouse
coordinates would be in window pixels, not image pixels. That reasoning
was wrong for the actual runtime (Windows, Win32 HighGUI backend):
`cv2.setMouseCallback` coordinates there are already converted back to
the original image's pixel space by cv2 itself whenever the window is
resized -- confirmed by the reported symptom (clicks became "confused"
after resizing), which is the exact signature of applying that
conversion a second time on top of coordinates cv2 had already
converted. So: pass the raw `(x, y)` straight through, same as the
original `WINDOW_AUTOSIZE` version -- only a defensive clamp against
the last-drawn frame's own bounds remains, purely to guard against
stray off-by-one/negative values at the very edge of the window rather
than to do any real rescaling.
"""
from __future__ import annotations

from typing import Optional, Tuple

import cv2

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.renderer import MouseHandler, Renderer

QUIT_KEYS = (27, ord('q'))  # Esc, q


class Cv2Renderer(Renderer):
    def __init__(self, window_name: str = "Kung Fu Chess", wait_ms: int = 1):
        self._window_name = window_name
        self._wait_ms = wait_ms
        self._native_w: Optional[int] = None
        self._native_h: Optional[int] = None
        cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)

    def draw_frame(self, frame: Img) -> None:
        self._native_h, self._native_w = frame.array.shape[:2]
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
        collaborator needs to know `cv2`'s event codes exist. Coordinates
        are forwarded as-is (see module docstring) -- cv2's own backend
        already keeps them in the original frame's pixel space even
        after the window is resized; only clamped to that frame's own
        bounds as cheap insurance."""
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
