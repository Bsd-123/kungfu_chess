"""`PieceRenderer` orchestrates interpolation and the per-piece
animation state machine over `motion_math`, `tracked_piece`,
`fading_ghost`, and `cooldown_overlay`. `is_real` is forwarded to
`SpriteLibrary` (`None` falls back to its own auto-detection)."""
from __future__ import annotations

import math
import time
from typing import Callable, Optional, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.ui.events.events import MoveResolvedEvent
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.piece.cooldown_overlay import draw_cooldown_overlay
from kungfu_chess.ui.rendering.piece.fading_ghost import FadingGhostPool
from kungfu_chess.ui.rendering.piece.motion_math import Correction, lerp
from kungfu_chess.ui.rendering.piece.tracked_piece import TrackedPieceRegistry
from kungfu_chess.ui.sprites.sprite_library import SpriteLibrary
from kungfu_chess.ui.theme import DEFAULT_THEME, PieceAnimationTheme
from kungfu_chess.view.game_snapshot import GameSnapshot, PieceSnapshot


class PieceRenderer:
    def __init__(self, asset_root: str, cell_pixel_size: int,
                 clock: Callable[[], float] = time.perf_counter,
                 offset: Tuple[int, int] = (0, 0),
                 theme: PieceAnimationTheme = DEFAULT_THEME.piece_animation,
                 is_real: Optional[bool] = None):
        """`offset`: screen-space pixel offset of the board's top-left
        cell. Internal calculations stay in board-space pixels; offset is
        added only at the final `frame.draw_on` call."""
        self._library = SpriteLibrary(asset_root, cell_pixel_size, is_real=is_real)
        self._cell = cell_pixel_size
        self._clock = clock
        self._offset = offset
        self._theme = theme
        self._last_tick: Optional[float] = None
        self._registry = TrackedPieceRegistry(self._library)
        self._ghosts = FadingGhostPool()

    def _dt_ms(self) -> float:
        now = self._clock()
        if self._last_tick is None:
            self._last_tick = now
            return 0.0
        dt = max(0.0, (now - self._last_tick) * 1000.0)
        self._last_tick = now
        return dt

    def _cell_of(self, piece: PieceSnapshot) -> Position:
        return Position(piece.pixel_y // self._cell, piece.pixel_x // self._cell)

    def _interpolated_position(self, piece: PieceSnapshot) -> Tuple[int, int]:
        if piece.state == "move" and piece.dst_pixel_x is not None:
            x = lerp(piece.pixel_x, piece.dst_pixel_x, piece.motion_progress)
            y = lerp(piece.pixel_y, piece.dst_pixel_y, piece.motion_progress)
            return x, y
        if piece.state == "jump":
            bump = int(round(self._theme.jump_hop_height_px *
                              math.sin(math.pi * piece.motion_progress)))
            # Clamp to avoid negative y: numpy silently wraps a negative
            # slice start instead of erroring, and Img.draw_on doesn't clip.
            return piece.pixel_x, max(0, piece.pixel_y - bump)
        return piece.pixel_x, piece.pixel_y

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        """Settlement-event hook via `EventBus`, fired before this tick's
        `draw()`, so `last_render_pos` still reflects the prior frame --
        the right start for a corrective slide. No-op if the move landed
        where requested, or for jumps."""
        if event.requested_dst_row is None or event.requested_dst_col is None:
            return
        if (event.requested_dst_row, event.requested_dst_col) == (event.dst_row, event.dst_col):
            return  # landed exactly where requested -- an ordinary settle

        src_cell = Position(event.src_row, event.src_col)
        dst_cell = Position(event.dst_row, event.dst_col)

        from_pos = self._registry.last_render_pos_at(src_cell)
        if from_pos is not None:
            from_x, from_y = from_pos
        else:
            # No frame was ever rendered (e.g. settled on the first tick) --
            # fall back to the requested destination's pixel position.
            from_x = event.requested_dst_col * self._cell
            from_y = event.requested_dst_row * self._cell

        to_x, to_y = event.dst_col * self._cell, event.dst_row * self._cell
        correction = Correction(from_x, from_y, to_x, to_y,
                                 duration_ms=self._theme.correction_duration_ms)
        self._registry.register_correction(src_cell, dst_cell, correction)

    def draw(self, frame: Img, snapshot: GameSnapshot) -> None:
        dt_ms = self._dt_ms()

        self._registry.step_corrections(dt_ms)

        off_x, off_y = self._offset
        seen = set()
        for piece in snapshot.pieces:
            cell = self._cell_of(piece)
            seen.add(cell)
            render_x, render_y = self._registry.update(
                piece, cell, dt_ms, self._interpolated_position)

            frame.draw_on(self._registry.current_frame(cell),
                           render_x + off_x, render_y + off_y)

            if piece.cooldown_progress is not None:
                draw_cooldown_overlay(frame, self._cell, render_x + off_x, render_y + off_y,
                                       piece.cooldown_progress, self._theme)

        # Only pieces genuinely swallowed mid-flight (not settled or
        # redirected) produce a fade-out ghost.
        vanished = self._registry.pop_vanished(seen)
        self._ghosts.spawn_if_swallowed(vanished, snapshot, self._offset)
        self._ghosts.step_and_draw(frame, dt_ms, self._theme.fade_duration_ms)
