from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class MoveResult:
    """Result shape mandated by Spec §9/§20. `reason` is always present:
    `"ok"` for an accepted command, or an application-level rejection
    code (`"game_over"`, `"motion_in_progress"`) or -- when the rejection
    happened deeper, inside RuleEngine -- the specific MoveValidation
    reason (`"outside_board"`, `"empty_source"`, `"friendly_destination"`,
    `"illegal_piece_move"`), copied through unchanged."""

    is_accepted: bool
    reason: str

    def __bool__(self) -> bool:
        # Non-breaking convenience: existing/future call sites that only
        # care about accept/reject (`if engine.request_move(...):`) keep
        # working, since MoveResult is truthy/falsy like the old bool.
        return self.is_accepted
