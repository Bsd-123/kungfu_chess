"""ABC for the display backend, so the game loop can swap in a fake
implementation for headless testing instead of `Cv2Renderer`."""
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
        """Returns False when the loop should stop (quit key/window closed)."""

    def register_mouse_handler(self, handler: MouseHandler) -> None:
        """Optional hook: wire `handler(x, y, clicked)` to the window; default no-op."""

    def close(self) -> None:
        """Optional teardown hook; default no-op."""
