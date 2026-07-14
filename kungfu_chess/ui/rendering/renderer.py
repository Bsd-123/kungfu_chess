"""`Renderer` -- thin Protocol/ABC for the display backend (plan section
7.1 directory tree). `BoardView`/the game loop only ever depend on this
interface, never on `cv2` directly, so the loop itself stays testable
headlessly (plan section 7.7: "every tests/ui/ test runs headless") by
swapping in a fake implementation instead of `Cv2Renderer`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from kungfu_chess.ui.img import Img

MouseHandler = Callable[[int, int, bool], None]


class Renderer(ABC):
    @abstractmethod
    def draw_frame(self, frame: Img) -> None:
        """Displays one already-rendered frame."""

    @abstractmethod
    def poll_events(self) -> bool:
        """Processes pending window events (keypress, close button,
        etc.) for this tick. Returns False when the loop should stop
        (quit key pressed / window closed), True to keep going."""

    def register_mouse_handler(self, handler: MouseHandler) -> None:
        """Optional hook (Phase 3): backends that support mouse input
        override this to wire `handler(x, y, clicked)` up to their
        window. `x`/`y` are pixel coordinates in the same space the
        rendered frame uses; `clicked` is True only on the event that
        should be forwarded to `Controller.click`. Default no-op, so
        headless test doubles (and any future non-interactive backend)
        don't need to implement mouse support at all."""

    def close(self) -> None:
        """Optional teardown hook; default no-op for backends (or fakes)
        that don't need one."""
