from __future__ import annotations
from typing import NamedTuple


class Position(NamedTuple):
    """Board-cell value object (Spec §6). Deliberately a NamedTuple rather
    than a plain dataclass: it gets equality, a readable repr, and
    hashability for free, but -- critically -- it also remains fully
    indexable/iterable (`pos[0]`, `pos[1]`, tuple unpacking) so every
    existing piece of engine code that already treats a Position as a
    2-tuple (`dst[0] - src[0]`, dict keys, etc.) keeps working unchanged.
    No board-bounds checking lives here; that is Board's job."""

    row: int
    col: int
