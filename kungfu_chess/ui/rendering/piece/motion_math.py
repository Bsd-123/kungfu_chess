"""Pure numeric helpers for `PieceRenderer`'s animation math -- no
dependency on `Img`/`SpriteLibrary`/`GameSnapshot`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


@dataclass
class Correction:
    """A corrective slide played instead of an instant snap when a
    settled move's true landing square differs from the one it was
    animating toward. `from_x/from_y` is wherever it was last rendered,
    so the slide starts with no visible pop; `to_x/to_y` is the true
    settled position."""
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    duration_ms: float
    elapsed_ms: float = 0.0

    def finished(self) -> bool:
        return self.elapsed_ms >= self.duration_ms

    def position(self) -> Tuple[int, int]:
        t = min(1.0, max(0.0, self.elapsed_ms / self.duration_ms)) if self.duration_ms > 0 else 1.0
        # Ease-out cubic: fast at first, smoothly decelerating into the
        # landing square.
        eased_t = 1.0 - (1.0 - t) ** 3
        return lerp(self.from_x, self.to_x, eased_t), lerp(self.from_y, self.to_y, eased_t)
