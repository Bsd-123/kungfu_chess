from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameConfig:
    """Centralized configuration. All magic numbers/strings used across the
    engine live here so they can be tuned or overridden (e.g. for a custom
    game variant) without touching business logic anywhere else."""

    cell_pixel_size: int = 100

    # Per-square travel time in ms, keyed by piece type. Used as the
    # multiplier in `duration = squares_traveled * per_square_ms`
    # (Spec §10: "Moving N squares takes N x 1000ms"). A piece type not
    # present here falls back to `default_move_duration_ms`. This dict
    # previously held a *flat* per-piece duration; it is now interpreted
    # as a *per-square* duration, which is a strict generalization: any
    # game whose pieces all move exactly one square already behaves
    # identically to before.
    move_duration_ms: dict = field(default_factory=dict)
    # TEMPORARY x2.5 slowdown (requested for easier testing/visibility --
    # revert both of these two numbers back to 1000 to restore normal
    # speed; nothing else in the engine depends on this specific value).
    default_move_duration_ms: int = 2500

    jump_duration_ms: int = 2500

    # Post-move cooldown (new feature): after a piece's motion settles,
    # it cannot start another motion from its landing square for this
    # long -- other pieces are completely unaffected. Keyed by piece
    # type the same way `move_duration_ms` is, falling back to
    # `default_cooldown_ms` for any type not present. `0` disables
    # cooldown entirely for that piece type (the pre-existing, always-
    # available-again-instantly behavior).
    # TEMPORARY x2 lengthening (requested for easier testing/visibility --
    # halve both of these two numbers back to 500/200 to restore the
    # original cooldown lengths; nothing else in the engine depends on
    # these specific values).
    cooldown_ms: dict = field(default_factory=dict)
    default_cooldown_ms: int = 1000

    # Post-jump cooldown: a separate, shorter recovery window for a jump
    # landing (as opposed to a completed slide/move). Same per-piece-
    # type-override-with-a-default shape as `cooldown_ms`/
    # `default_cooldown_ms` above, kept as its own pair rather than
    # reusing the move ones so a jump's recovery can be tuned
    # independently -- a jump is a much shorter, snappier action than a
    # multi-square slide, so its landing square shouldn't have to wait
    # just as long before it can act again.
    jump_cooldown_ms: dict = field(default_factory=dict)
    default_jump_cooldown_ms: int = 400

    empty_token: str = '.'
    board_marker: str = 'Board:'
    commands_marker: str = 'Commands:'
    print_board_command: str = 'print board'
    token_pattern: str = r'^(?:\.|[wb][KQRBNP])$'
