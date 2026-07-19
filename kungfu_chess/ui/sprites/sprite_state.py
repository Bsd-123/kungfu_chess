"""One `SpriteState` per named animation, each with its own frame list
and `StateConfig` (fps, loop, next-state-when-finished). New states
only need a new asset folder + config, no code changes here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from kungfu_chess.ui.img import Img


@dataclass(frozen=True)
class StateConfig:
    fps: float
    loop: bool
    next_state_when_finished: Optional[str] = None


class SpriteState:
    def __init__(self, name: str, frames: List[Img], config: StateConfig):
        if not frames:
            raise ValueError(f"SpriteState '{name}': no frames given")
        self.name = name
        self.frames = frames
        self.config = config
        self._elapsed_ms = 0.0

    def _frame_index(self) -> int:
        frame_duration = 1000.0 / self.config.fps
        index = int(self._elapsed_ms // frame_duration)
        if self.config.loop:
            return index % len(self.frames)
        return min(index, len(self.frames) - 1)

    def advance(self, dt_ms: float) -> Optional[str]:
        """Returns the next state name if a non-looping state just finished this tick, else None."""
        self._elapsed_ms += dt_ms
        if self.config.loop:
            return None
        frame_duration = 1000.0 / self.config.fps
        finished = self._elapsed_ms >= frame_duration * len(self.frames)
        return self.config.next_state_when_finished if finished else None

    def current_frame(self) -> Img:
        return self.frames[self._frame_index()]
