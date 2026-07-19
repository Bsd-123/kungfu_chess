from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from kungfu_chess.model.position import Position


@dataclass(frozen=True)
class PieceSnapshot:
    """Read-only per-piece view data; no board coords or live Piece reference.
    `motion_progress`: 0.0->1.0 fraction of an in-flight motion elapsed.
    `pixel_x`/`pixel_y` stay pinned to the source cell during a move (settlement is
    atomic); `dst_pixel_x`/`dst_pixel_y` give the target so a renderer can glide.
    `cooldown_progress`: 0.0->1.0 of post-move cooldown, or None if not cooling down."""

    kind: str
    color: str
    pixel_x: int
    pixel_y: int
    state: str
    motion_progress: float = 1.0
    dst_pixel_x: Optional[int] = None
    dst_pixel_y: Optional[int] = None
    cooldown_progress: Optional[float] = None


@dataclass(frozen=True)
class GameSnapshot:
    """The one thing a Renderer is allowed to see; built fresh by `GameEngine.snapshot()`,
    entirely immutable plain values."""

    board_width: int
    board_height: int
    pieces: List[PieceSnapshot]
    selected: Optional[Position]
    game_over: bool

    # 'w'/'b' whose move triggered the win, or None while the game hasn't ended.
    winner: Optional[str] = None
