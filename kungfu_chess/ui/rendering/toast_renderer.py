""""Game Over" toast that bounces onto the board when
`GameSnapshot.game_over` flips true. Built once as a small BGRA `Img`
and alpha-composited onto the frame at an animated `y` position."""
from __future__ import annotations

import time
from typing import Callable, Optional, Tuple

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.theme import DEFAULT_THEME, ToastTheme
from kungfu_chess.view.game_snapshot import GameSnapshot


def _ease_out_bounce(t: float) -> float:
    """Standard bounce-out easing: rises to 1.0 with two diminishing
    overshoot bounces rather than settling smoothly."""
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
                 clock: Callable[[], float] = time.perf_counter,
                 player_names: Tuple[str, str] = ("White", "Black"),
                 theme: ToastTheme = DEFAULT_THEME.toast):
        """`center_x`/`center_y`: rest position. `player_names` is
        `(white_name, black_name)`, mapped from `GameSnapshot.winner`'s
        `'w'`/`'b'` code."""
        self._center_x = center_x
        self._center_y = center_y
        self._clock = clock
        self._player_names = player_names
        self._theme = theme
        self._start_time: Optional[float] = None
        self._toast: Optional[Img] = None

    def _winner_name(self, winner: Optional[str]) -> Optional[str]:
        white_name, black_name = self._player_names
        if winner == 'w':
            return white_name
        if winner == 'b':
            return black_name
        return None

    def _build_toast(self, winner: Optional[str]) -> Img:
        """Built fresh once per game-over transition (winner unknown until then)."""
        theme = self._theme
        winner_name = self._winner_name(winner)
        lines = ["GAME OVER"]
        if winner_name is not None:
            lines.append(f"{winner_name} Wins!")

        box = Img.new(theme.box_width, theme.box_height, channels=4, color=theme.box_bg_color)
        box.draw_rect(0, 0, theme.box_width - 1, theme.box_height - 1,
                       theme.box_border_color, thickness=3)

        if len(lines) == 1:
            text_w, text_h = box.text_size(lines[0], font_scale=theme.title_font_scale,
                                            thickness=theme.text_thickness)
            box.put_text(lines[0], theme.box_width // 2 - text_w // 2,
                          theme.box_height // 2 + text_h // 2, theme.text_color,
                          font_scale=theme.title_font_scale, thickness=theme.text_thickness)
        else:
            title_w, title_h = box.text_size(lines[0], font_scale=theme.title_font_scale,
                                              thickness=theme.text_thickness)
            box.put_text(lines[0], theme.box_width // 2 - title_w // 2,
                          theme.box_height // 2 - theme.subtitle_gap_px, theme.text_color,
                          font_scale=theme.title_font_scale, thickness=theme.text_thickness)

            sub_w, sub_h = box.text_size(lines[1], font_scale=theme.subtitle_font_scale,
                                          thickness=theme.text_thickness)
            box.put_text(lines[1], theme.box_width // 2 - sub_w // 2,
                          theme.box_height // 2 + theme.subtitle_gap_px + sub_h, theme.text_color,
                          font_scale=theme.subtitle_font_scale, thickness=theme.text_thickness)
        return box

    def draw(self, frame: Img, snapshot: GameSnapshot) -> None:
        if not snapshot.game_over:
            # Reset so the next game replays the bounce-in with the right winner.
            self._start_time = None
            self._toast = None
            return

        theme = self._theme
        now = self._clock()
        if self._start_time is None:
            self._start_time = now
            self._toast = self._build_toast(snapshot.winner)
        elapsed_ms = (now - self._start_time) * 1000.0
        progress = min(1.0, elapsed_ms / theme.duration_ms)
        eased = _ease_out_bounce(progress)

        # Clamp to frame bounds -- Img.draw_on does not clip.
        rest_x = max(0, min(frame.width - theme.box_width, self._center_x - theme.box_width // 2))
        rest_y = max(0, min(frame.height - theme.box_height, self._center_y - theme.box_height // 2))
        start_y = rest_y - theme.drop_distance_px
        y = int(round(start_y + (rest_y - start_y) * eased))
        y = max(0, min(frame.height - theme.box_height, y))

        frame.draw_on(self._toast, rest_x, y)
