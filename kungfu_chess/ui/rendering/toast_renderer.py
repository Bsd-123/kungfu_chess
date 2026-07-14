"""Fifth (optional) `BoardView` collaborator: a "Game Over" toast that
bounces onto the board when `GameSnapshot.game_over` flips true. Reads
`game_over` straight off the snapshot -- Rule 11's King-capture trigger
(`GameEngine.settle`) already sets it there, so no new wiring back to
the engine is needed, just one more optional draw step in `BoardView`.

The bounce-in entrance reuses the same "no PyGame, just cv2 primitives
composited via `Img`" philosophy as every other renderer here: the
toast is built once as its own small BGRA `Img` (translucent background
+ opaque text), then alpha-composited onto the frame via `Img.draw_on`
at an animated `y` position (the same alpha-blend path `PieceRenderer`
uses for its swallow-fade ghosts), rather than drawn directly with
`draw_rect`/`put_text` straight onto the frame -- `draw_rect` does a
hard pixel overwrite, not a blend, so a translucent background only
looks translucent if it's composited in via `draw_on`."""
from __future__ import annotations

import time
from typing import Callable, Optional

from kungfu_chess.ui.img import Img
from kungfu_chess.view.game_snapshot import GameSnapshot

BOX_WIDTH = 320
BOX_HEIGHT = 110
BOX_BG_COLOR = (20, 20, 20, 225)      # BGRA, translucent dark background
BOX_BORDER_COLOR = (60, 220, 255)     # BGR, amber -- matches the piece move-highlight ring
TEXT_COLOR = (245, 245, 245)

DROP_DISTANCE_PX = 140
DURATION_MS = 900.0


def _ease_out_bounce(t: float) -> float:
    """Standard bounce-out easing (easings.net): rises to 1.0 with two
    diminishing overshoot bounces rather than settling smoothly, which
    is what makes the toast read as "jumping" onto the board instead of
    just sliding or fading in."""
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


class ToastRenderer:
    def __init__(self, center_x: int, center_y: int,
                 clock: Callable[[], float] = time.perf_counter):
        """`center_x`/`center_y` -- screen-space point the toast is
        centered on at rest (typically the board's own center, passed
        in by the composition root). `clock` mirrors `PieceRenderer`'s
        own DI pattern, so the bounce timing is independently testable
        with a fake clock rather than tied to real wall time."""
        self._center_x = center_x
        self._center_y = center_y
        self._clock = clock
        self._start_time: Optional[float] = None
        self._toast = self._build_toast()

    def _build_toast(self) -> Img:
        box = Img.new(BOX_WIDTH, BOX_HEIGHT, channels=4, color=BOX_BG_COLOR)
        box.draw_rect(0, 0, BOX_WIDTH - 1, BOX_HEIGHT - 1, BOX_BORDER_COLOR, thickness=3)
        text = "GAME OVER"
        text_w, text_h = box.text_size(text, font_scale=1.0, thickness=2)
        box.put_text(text, BOX_WIDTH // 2 - text_w // 2, BOX_HEIGHT // 2 + text_h // 2,
                      TEXT_COLOR, font_scale=1.0, thickness=2)
        return box

    def draw(self, frame: Img, snapshot: GameSnapshot) -> None:
        if not snapshot.game_over:
            # Not (or no longer) game-over -- reset so a fresh game
            # replays the bounce-in rather than snapping straight to
            # the resting position on the next game-over.
            self._start_time = None
            return

        now = self._clock()
        if self._start_time is None:
            self._start_time = now
        elapsed_ms = (now - self._start_time) * 1000.0
        progress = min(1.0, elapsed_ms / DURATION_MS)
        eased = _ease_out_bounce(progress)

        # Clamp against the actual frame size (not just the layout this
        # was constructed with) -- cheap insurance against `Img.draw_on`'s
        # deliberate no-clipping behavior (plan section 3 plumbing note 4)
        # if the frame ever ends up smaller than the toast box.
        rest_x = max(0, min(frame.width - BOX_WIDTH, self._center_x - BOX_WIDTH // 2))
        rest_y = max(0, min(frame.height - BOX_HEIGHT, self._center_y - BOX_HEIGHT // 2))
        start_y = rest_y - DROP_DISTANCE_PX
        y = int(round(start_y + (rest_y - start_y) * eased))
        y = max(0, min(frame.height - BOX_HEIGHT, y))

        frame.draw_on(self._toast, rest_x, y)
