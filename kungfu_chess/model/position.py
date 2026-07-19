from __future__ import annotations
from typing import NamedTuple


class Position(NamedTuple):
    """Board-cell value object; no bounds checking (that's the Board's job)."""

    row: int
    col: int
