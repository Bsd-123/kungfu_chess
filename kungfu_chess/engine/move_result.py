from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class MoveResult:
    """`reason` is always present: `"ok"`, an application-level rejection code
    (`"game_over"`, `"motion_in_progress"`), or a RuleEngine `MoveValidation`
    reason copied through unchanged."""

    is_accepted: bool
    reason: str

    def __bool__(self) -> bool:
        # Lets call sites use `if engine.request_move(...):` directly.
        return self.is_accepted
