from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from kungfu_chess.model.position import Position


@dataclass(frozen=True)
class PieceSnapshot:
    """Read-only per-piece view data (Spec §12): kind/color/pixel
    position/state -- nothing else. No board coordinates, no live Piece
    reference, so nothing here can be used to mutate the model."""

    kind: str
    color: str
    pixel_x: int
    pixel_y: int
    state: str


@dataclass(frozen=True)
class GameSnapshot:
    """The one thing a Renderer is allowed to see (Spec §12/§20). Built
    fresh by `GameEngine.snapshot()` from current logical board state;
    holding onto an old snapshot never lets you mutate anything, since
    every field here is a plain, immutable value."""

    board_width: int
    board_height: int
    pieces: List[PieceSnapshot]
    selected: Optional[Position]
    game_over: bool
