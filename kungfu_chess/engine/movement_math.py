from __future__ import annotations

from kungfu_chess.model.position import Position

__all__ = ["squares_traveled"]


def squares_traveled(src: Position, dst: Position) -> int:
    """Chebyshev distance in cells (max(|dr|,|dc|)), so a diagonal move counts
    diagonal steps rather than double-counting row+col like Manhattan distance."""
    dr = abs(dst[0] - src[0])
    dc = abs(dst[1] - src[1])
    return max(dr, dc, 1)
