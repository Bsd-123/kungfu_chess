"""`Img` -- thin `cv2`-backed image wrapper used for all rendering.
`draw_on` alpha-blends only if both images are BGRA, does no clipping,
and mutates `self` in place; `show()` blocks and isn't for per-frame use."""
from __future__ import annotations

import os
from typing import Optional, Tuple

import cv2
import numpy as np

from kungfu_chess.ui.theme import DEFAULT_THEME


class Img:
    """Wraps a single `numpy` array (`self.array`), BGR (3-channel) or
    BGRA (4-channel)."""

    def __init__(self, array: Optional[np.ndarray] = None):
        self.array: Optional[np.ndarray] = array

    # -- construction ------------------------------------------------
    def read(self, path: str, size: Optional[Tuple[int, int]] = None,
              keep_aspect: bool = False) -> "Img":
        """Loads an image (alpha preserved), decoding via `np.fromfile`
        + `cv2.imdecode` instead of `cv2.imread` because `cv2.imread`
        silently returns None for non-ASCII paths on Windows. Optionally
        resizes to `size`; `keep_aspect=True` letterboxes instead of
        stretching."""
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Img.read: no such file '{path}'")

        data = np.fromfile(path, dtype=np.uint8)
        array = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        if array is None:
            raise FileNotFoundError(
                f"Img.read: found '{path}' but could not decode it as an image")
        self.array = array

        if size is not None:
            self._resize_to(size, keep_aspect)
        return self

    @classmethod
    def new(cls, width: int, height: int, channels: int = 4,
            color: Tuple[int, ...] = (0, 0, 0, 0)) -> "Img":
        """Blank canvas filled with `color`."""
        array = np.zeros((height, width, channels), dtype=np.uint8)
        array[:, :] = color[:channels]
        return cls(array)

    def copy(self) -> "Img":
        """Independent copy, safe to mutate."""
        return Img(self.array.copy())

    # -- channel/size handling ----------------------------------------
    def to_bgra(self) -> "Img":
        """Forces 4-channel (BGRA) in place; opaque alpha added if source
        was 3-channel."""
        if self.channels == 3:
            self.array = cv2.cvtColor(self.array, cv2.COLOR_BGR2BGRA)
        return self

    def _resize_to(self, size: Tuple[int, int], keep_aspect: bool) -> None:
        target_w, target_h = size
        h, w = self.array.shape[:2]

        if not keep_aspect:
            self.array = cv2.resize(self.array, (target_w, target_h),
                                     interpolation=cv2.INTER_AREA)
            return

        scale = min(target_w / w, target_h / h)
        new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
        resized = cv2.resize(self.array, (new_w, new_h),
                              interpolation=cv2.INTER_AREA)

        self.to_bgra()
        canvas = Img.new(target_w, target_h, channels=4, color=(0, 0, 0, 0))
        x_off = (target_w - new_w) // 2
        y_off = (target_h - new_h) // 2

        resized_img = Img(resized)
        resized_img.to_bgra()
        canvas.draw_on(resized_img, x_off, y_off)
        self.array = canvas.array

    @property
    def width(self) -> int:
        return self.array.shape[1]

    @property
    def height(self) -> int:
        return self.array.shape[0]

    @property
    def channels(self) -> int:
        return self.array.shape[2] if self.array.ndim == 3 else 1

    # -- compositing ---------------------------------------------------
    def draw_on(self, other: "Img", x: int, y: int) -> "Img":
        """Draws `other` onto `self` at top-left `(x, y)`, mutating `self`
        in place. Alpha-blends only if both are 4-channel, otherwise
        plain-overwrites; no clipping, `other` must fit."""
        h, w = other.array.shape[:2]
        dest = self.array[y:y + h, x:x + w]

        if self.channels == 4 and other.channels == 4:
            src_rgb = other.array[:, :, :3].astype(np.float32)
            src_a = (other.array[:, :, 3:4].astype(np.float32)) / 255.0
            dest_rgb = dest[:, :, :3].astype(np.float32)
            dest_a = (dest[:, :, 3:4].astype(np.float32)) / 255.0

            out_a = src_a + dest_a * (1.0 - src_a)
            with np.errstate(invalid="ignore", divide="ignore"):
                out_rgb = np.where(
                    out_a > 0,
                    (src_rgb * src_a + dest_rgb * dest_a * (1.0 - src_a)) /
                    np.clip(out_a, 1e-6, None),
                    0.0,
                )

            dest[:, :, :3] = out_rgb.astype(np.uint8)
            dest[:, :, 3:4] = (out_a * 255.0).astype(np.uint8)
        else:
            dest[:, :, :] = other.array[:, :, :dest.shape[2]]

        return self

    # -- primitive drawing ----------------------------------------------
    def _full_color(self, color: Tuple[int, ...]) -> Tuple[int, ...]:
        """`cv2` pads a short color with zeros (transparent), not opaque;
        pad BGR colors with 255 alpha explicitly on BGRA images."""
        if self.channels == 4 and len(color) == 3:
            return (*color, 255)
        return color

    def draw_rect(self, x1: int, y1: int, x2: int, y2: int,
                   color: Tuple[int, ...], thickness: int = -1) -> "Img":
        cv2.rectangle(self.array, (x1, y1), (x2, y2),
                      self._full_color(color), thickness)
        return self

    def draw_circle(self, cx: int, cy: int, radius: int,
                     color: Tuple[int, ...], thickness: int = -1) -> "Img":
        cv2.circle(self.array, (cx, cy), radius,
                   self._full_color(color), thickness)
        return self

    def draw_ellipse(self, cx: int, cy: int, axes: Tuple[int, int],
                      color: Tuple[int, ...], angle: float = 0.0,
                      start_angle: float = 0.0, end_angle: float = 360.0,
                      thickness: int = -1) -> "Img":
        """`axes = (rx, ry)`. `start_angle`/`end_angle` in degrees (cv2
        convention, 0 = 3 o'clock, clockwise); default `thickness=-1`
        fills a pie-slice wedge (used for the cooldown wheel)."""
        cv2.ellipse(self.array, (cx, cy), axes, angle, start_angle, end_angle,
                    self._full_color(color), thickness)
        return self

    def draw_polygon(self, points: Tuple[Tuple[int, int], ...],
                      color: Tuple[int, ...], thickness: int = -1) -> "Img":
        """`thickness=-1` fills the polygon; positive thickness draws
        just the closed outline."""
        pts = np.array([points], dtype=np.int32)
        if thickness == -1:
            cv2.fillPoly(self.array, pts, self._full_color(color))
        else:
            cv2.polylines(self.array, pts, True, self._full_color(color), thickness)
        return self

    def draw_line(self, x1: int, y1: int, x2: int, y2: int,
                   color: Tuple[int, ...], thickness: int = 2) -> "Img":
        cv2.line(self.array, (x1, y1), (x2, y2),
                 self._full_color(color), thickness)
        return self

    def put_text(self, text: str, x: int, y: int, color: Tuple[int, ...],
                  font_scale: float = 1.0, thickness: int = 2,
                  font: int = cv2.FONT_HERSHEY_SIMPLEX) -> "Img":
        cv2.putText(self.array, text, (x, y), font, font_scale,
                   self._full_color(color), thickness, cv2.LINE_AA)
        return self

    @staticmethod
    def text_size(text: str, font_scale: float = 1.0, thickness: int = 2,
                   font: int = cv2.FONT_HERSHEY_SIMPLEX) -> Tuple[int, int]:
        """`(width, height)` in pixels `text` would occupy via `put_text`
        with the same params; pure query, draws nothing."""
        (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        return w, h

    # -- output -----------------------------------------------------------
    def save(self, path: str) -> "Img":
        """Encodes in memory and writes via a Unicode-safe file handle
        (not `cv2.imwrite`), for the same non-ASCII-path reason as `read()`."""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        ext = os.path.splitext(path)[1] or ".png"
        ok, encoded = cv2.imencode(ext, self.array)
        if not ok:
            raise IOError(f"Img.save: failed to encode image for '{path}'")
        encoded.tofile(path)
        return self

    def show(self, window_name: str = DEFAULT_THEME.window.window_name,
              wait_ms: int = 0) -> None:
        """Blocking (`cv2.waitKey(0)`) -- for one-off checks only, not a
        per-frame loop."""
        cv2.imshow(window_name, self.array)
        cv2.waitKey(wait_ms)
        cv2.destroyWindow(window_name)
