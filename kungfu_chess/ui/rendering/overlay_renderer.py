"""Third `BoardView` collaborator (plan section 7.2a / directory tree):
selection highlight, explicitly decoupled from board background
rendering (`BoardRenderer`) and piece compositing (`PieceRenderer`) --
a Phase 6 rejection tooltip, for example, only ever needs to touch
this file.

Draws the selection highlight from `InputState.selected`, which the
game loop fills in from **`controller.selected`** -- confirmed the only
live selection source (final_plan_verified.md section 0.4 / Phase 3
step 6). Never wire this to `snapshot.selected`: `Controller.click()`
tracks its own private `_selected` and never writes back to
`engine.selected`, so `snapshot.selected` is always `None` in the
current engine.

`InputState` still carries `cursor_pos`/`last_click_pos` (`MouseRouter`
tracks them regardless), but this renderer no longer draws them --
the yellow live-cursor dot and red last-click ring were debug markers
from Phase 3 plumbing, not part of the actual game UI, and are gone
per request. Left the fields in place rather than ripping them out of
`MouseRouter`/`InputState` too, since some future debug overlay could
still want them without re-threading the mouse-tracking plumbing.

Movement-range highlight feature: `InputState.legal_destinations` is
computed once per frame by the game loop (`ui/app.py`'s `run_loop`), via
`GameEngine.legal_destinations(controller.selected)` -- the same
established "loop asks the engine, builds a plain-value `InputState`,
hands it to this renderer" pipeline `selected` itself already uses, so
this stays a pure coordinate-translation + drawing concern here and
never reaches back into the engine/rules layer on its own.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.ui.img import Img
from kungfu_chess.view.game_snapshot import GameSnapshot

SELECTION_COLOR = (0, 200, 0)       # BGR green, selection square outline
MOVE_HIGHLIGHT_COLOR = (0, 255, 255)  # BGR yellow, legal-destination highlight

# Animated half-opacity fill (replaces the earlier thin-outline-plus-dot
# style): alpha breathes on a slow sine wave between
# (BASE - AMPLITUDE) and (BASE + AMPLITUDE), out of 255, so the
# highlighted squares read as gently "alive" rather than a flat static
# wash of color -- the same breathing spirit as PieceRenderer's idle
# animation, just applied to alpha instead of a sprite frame.
# BASE=128 centers the pulse on true half-opacity, as requested.
MOVE_HIGHLIGHT_BASE_ALPHA = 128
MOVE_HIGHLIGHT_PULSE_AMPLITUDE = 40
MOVE_HIGHLIGHT_PULSE_PERIOD_MS = 1400.0


@dataclass(frozen=True)
class InputState:
    """Everything `OverlayRenderer` needs to draw a frame's selection +
    movement-range overlay -- built fresh each tick by the game loop
    from `Controller`/`MouseRouter`/`GameEngine`, never stored on the
    engine side.

    `legal_destinations` (movement-range highlight feature): every
    square the currently selected piece could legally move or jump to
    right now, in board-space `Position`s -- `()` whenever nothing is
    selected. Defaults to an empty tuple so this stays additive/
    backward-compatible with any existing construction of `InputState`."""
    selected: Optional[Position]
    cursor_pos: Optional[Tuple[int, int]]
    last_click_pos: Optional[Tuple[int, int]]
    legal_destinations: Sequence[Position] = ()


class OverlayRenderer:
    def __init__(self, cell_pixel_size: int, offset: Tuple[int, int] = (0, 0),
                 clock: Callable[[], float] = time.perf_counter):
        """`offset` (task 16): board-space screen offset applied to the
        selection highlight, which is computed from a board `Position`
        (`InputState.selected`, board-space). `clock` (movement-range
        highlight animation) drives the legal-destination pulse's phase
        -- same injected-clock pattern `PieceRenderer`/`ToastRenderer`
        already use, so this stays swappable/fake-able in tests without
        depending on real wall-clock time."""
        self._cell = cell_pixel_size
        self._offset = offset
        self._clock = clock

    def draw(self, frame: Img, snapshot: GameSnapshot,
              input_state: Optional[InputState]) -> None:
        if input_state is None or input_state.selected is None:
            return

        row, col = input_state.selected
        off_x, off_y = self._offset
        x1, y1 = off_x + col * self._cell, off_y + row * self._cell
        frame.draw_rect(x1, y1, x1 + self._cell - 1, y1 + self._cell - 1,
                         SELECTION_COLOR, thickness=3)

        if input_state.legal_destinations:
            alpha = self._pulse_alpha()
            for dest in input_state.legal_destinations:
                self._draw_move_highlight(frame, dest, alpha)

    def _pulse_alpha(self) -> int:
        """Alpha for this frame's legal-destination fill: a slow sine
        wave breathing between `MOVE_HIGHLIGHT_BASE_ALPHA -
        MOVE_HIGHLIGHT_PULSE_AMPLITUDE` and `... + ...`, out of 255.
        Computed once per `draw()` call (not per square) so every
        highlighted square pulses perfectly in sync with the others."""
        t_ms = self._clock() * 1000.0
        phase = (t_ms % MOVE_HIGHLIGHT_PULSE_PERIOD_MS) / MOVE_HIGHLIGHT_PULSE_PERIOD_MS
        wave = math.sin(2 * math.pi * phase)
        alpha = MOVE_HIGHLIGHT_BASE_ALPHA + MOVE_HIGHLIGHT_PULSE_AMPLITUDE * wave
        return int(max(0, min(255, round(alpha))))

    def _draw_move_highlight(self, frame: Img, cell: Position, alpha: int) -> None:
        """One legal-destination square: a translucent yellow fill
        covering the whole square (replacing the earlier thin-outline-
        plus-dot style), alpha-blended via `Img.draw_on` -- a piece
        sitting there (a capture target) still shows clearly through the
        half-opacity wash rather than being hidden under a solid color.
        A tiny `cell x cell` BGRA tile is the simplest way to reuse
        `draw_on`'s existing per-pixel alpha compositing (Spec/plan
        constraint: `Img` stays the one graphics primitive everything
        goes through) rather than hand-rolling a second blending path
        here."""
        row, col = cell
        off_x, off_y = self._offset
        x1, y1 = off_x + col * self._cell, off_y + row * self._cell

        tile = Img.new(self._cell, self._cell, channels=4,
                        color=(*MOVE_HIGHLIGHT_COLOR, alpha))
        frame.draw_on(tile, x1, y1)
