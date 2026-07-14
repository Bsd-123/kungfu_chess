from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from kungfu_chess.model.position import Position


@dataclass(frozen=True)
class PieceSnapshot:
    """Read-only per-piece view data (Spec section 12): kind/color/pixel
    position/state -- nothing else. No board coordinates, no live Piece
    reference, so nothing here can be used to mutate the model.

    Phase 4 additions (final_plan_verified.md section 7.5), both
    backward-compatible (default to the old idle-only behavior):

    `motion_progress`: 0.0 -> 1.0 fraction of an in-flight motion's
    duration elapsed, so a renderer can interpolate/animate without a
    separate per-piece query call.

    `dst_pixel_x`/`dst_pixel_y`: the destination cell's pixel position
    while `state == "move"`, else None. NOT part of the plan's literal
    illustrative patch in section 7.5 (which only added
    `motion_progress`) -- added because without a destination, a
    renderer has no way to glide a piece anywhere: `pixel_x`/`pixel_y`
    stay pinned to the *source* cell for the entire flight (Rule 10:
    settlement is atomic, so the board -- and this snapshot -- only
    ever shows the old position until the instant it lands), and
    `motion_progress` alone describes a timing fraction, not a
    direction. This is the same small, additive, backward-compatible
    shape as the rest of this patch (defaults to None so anything
    written against the original section 7.5 fields still works)."""

    kind: str
    color: str
    pixel_x: int
    pixel_y: int
    state: str
    motion_progress: float = 1.0
    dst_pixel_x: Optional[int] = None
    dst_pixel_y: Optional[int] = None


@dataclass(frozen=True)
class GameSnapshot:
    """The one thing a Renderer is allowed to see (Spec section 12/20). Built
    fresh by `GameEngine.snapshot()` from current logical board state;
    holding onto an old snapshot never lets you mutate anything, since
    every field here is a plain, immutable value."""

    board_width: int
    board_height: int
    pieces: List[PieceSnapshot]
    selected: Optional[Position]
    game_over: bool
