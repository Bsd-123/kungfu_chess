"""`Img` -- the one graphics primitive every visual in this app goes
through (final_plan_verified.md hard constraint: no PyGame/SFML/etc.,
just a thin `cv2` wrapper). Open to grow new methods as later phases
need them, as long as each stays a thin `cv2`-backed method here.

Plumbing notes this class embodies (plan section 3):
1. `show()` is blocking (`cv2.waitKey(0)`) -- fine for one-off checks,
   not for a per-frame loop (Phase 2+ drives `cv2.imshow`/`waitKey(1)`
   directly instead of calling `show()`).
3. `draw_on` only alpha-blends when both images are 4-channel (BGRA) --
   callers must force BGRA right after `read()`/`new()` if blending is
   wanted (`to_bgra()` below).
4. `draw_on` does no clipping -- callers are responsible for sizing
   sprites to fit exactly (e.g. every piece sprite == cell_pixel_size).
5. `draw_on` mutates `self` in place -- keep one pristine template and
   `.copy()` it fresh each frame rather than drawing onto the original.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import cv2
import numpy as np


class Img:
    """Thin `cv2`-backed image wrapper. Wraps a single `numpy` array
    (`self.array`) in either BGR (3-channel) or BGRA (4-channel) form,
    matching whatever `cv2` handed back / whatever was requested."""

    def __init__(self, array: Optional[np.ndarray] = None):
        self.array: Optional[np.ndarray] = array

    # -- construction ------------------------------------------------
    def read(self, path: str, size: Optional[Tuple[int, int]] = None,
              keep_aspect: bool = False) -> "Img":
        """Loads an image from disk, alpha channel preserved if present
        (`cv2.IMREAD_UNCHANGED`). Reads raw bytes via `numpy`'s own
        (Unicode-safe) file I/O and decodes them with `cv2.imdecode`
        rather than calling `cv2.imread(path, ...)` directly --
        `cv2.imread` opens the file through OpenCV's own path handling
        on Windows and silently returns None (not an exception) for any
        path containing non-ASCII characters, e.g. a Windows username
        with non-Latin letters, even though the same file opens fine in
        any other viewer. `np.fromfile` sidesteps that entirely.
        Optionally resizes to `size = (width, height)`; `keep_aspect=True`
        letterboxes onto a transparent canvas of exactly `size` instead
        of stretching."""
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
        """Blank canvas of the given size/channel depth, filled with
        `color` (BGR or BGRA, matching `channels`)."""
        array = np.zeros((height, width, channels), dtype=np.uint8)
        array[:, :] = color[:channels]
        return cls(array)

    def copy(self) -> "Img":
        """Independent copy -- safe to mutate without touching self."""
        return Img(self.array.copy())

    # -- channel/size handling ----------------------------------------
    def to_bgra(self) -> "Img":
        """Forces 4-channel (BGRA) in place, returns self for chaining.
        A 3-channel (BGR) source gets a fully-opaque alpha channel
        added; already-4-channel arrays are left untouched."""
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
        """Draws `other` onto `self` at top-left pixel `(x, y)`,
        mutating `self` in place (note 5) and returning self for
        chaining. Alpha-blends only if both images are 4-channel (note
        3); otherwise falls back to a plain overwrite of the region, so
        a caller who forgets to `to_bgra()` gets an obviously-wrong
        opaque paste rather than a silent no-op. No clipping (note 4):
        `other` must fit inside `self` at `(x, y)`."""
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
        """`cv2`'s drawing functions pad a short color scalar with
        *zeros*, not "leave unchanged" -- passing a 3-tuple BGR color on
        a 4-channel (BGRA) image silently zeroes the alpha channel
        (fully transparent), not "fully opaque" as you'd expect. Pad
        explicitly with 255 (opaque) instead so callers can keep passing
        plain BGR tuples without landing invisible on a BGRA canvas."""
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
                      thickness: int = -1) -> "Img":
        """`axes = (rx, ry)` -- half-width/half-height, matching cv2's
        own convention. Added for Phase 4 placeholder animation frames
        (squash/stretch jump poses) -- same thin cv2-wrapper philosophy
        as every other primitive here."""
        cv2.ellipse(self.array, (cx, cy), axes, angle, 0, 360,
                    self._full_color(color), thickness)
        return self

    def draw_polygon(self, points: Tuple[Tuple[int, int], ...],
                      color: Tuple[int, ...], thickness: int = -1) -> "Img":
        """`points` is a sequence of `(x, y)` vertices. `thickness=-1`
        fills the polygon (`cv2.fillPoly`); any positive thickness draws
        just the outline (`cv2.polylines`, closed). Added for chess-
        piece silhouettes (rook crenellations, knight head, crowns) --
        shapes `draw_circle`/`draw_rect`/`draw_ellipse` alone can't
        express, still a thin cv2 wrapper."""
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
        """`(width, height)` in pixels that `text` would occupy if drawn
        with `put_text` using these same params -- lets callers center
        text (panel headers, side-panel name boxes) without hand-tuned
        magic-number offsets. Pure query, draws nothing; still a thin
        wrapper (`cv2.getTextSize`), same philosophy as every other
        method on this class."""
        (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        return w, h

    # -- output -----------------------------------------------------------
    def save(self, path: str) -> "Img":
        """Encodes in memory and writes the bytes out via a plain
        Unicode-safe file handle rather than `cv2.imwrite(path, ...)`,
        for the same reason as `read()` above -- keeps write and read
        symmetric so a non-ASCII path behaves identically either way
        instead of one silently working and the other silently failing."""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        ext = os.path.splitext(path)[1] or ".png"
        ok, encoded = cv2.imencode(ext, self.array)
        if not ok:
            raise IOError(f"Img.save: failed to encode image for '{path}'")
        encoded.tofile(path)
        return self

    def show(self, window_name: str = "Kung Fu Chess",
              wait_ms: int = 0) -> None:
        """Blocking by default (note 1) -- `cv2.waitKey(0)` waits for a
        keypress. Only appropriate for one-off checks (Phase 1); a
        real-time loop (Phase 2+) should drive `cv2.imshow`/`waitKey(1)`
        itself instead of calling this per frame."""
        cv2.imshow(window_name, self.array)
        cv2.waitKey(wait_ms)
        cv2.destroyWindow(window_name)
