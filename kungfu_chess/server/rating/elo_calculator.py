"""Pure ELO functions (Decision 4): the standard logistic expected-score
formula with a single fixed, configured K-factor -- no swappable
strategy, no per-opponent-difficulty branching. Decision 12 means
`actual` is always exactly 1.0 (win) or 0.0 (loss, including a forfeit);
there is no 0.5 draw path anywhere in this module."""
from __future__ import annotations


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_rating(rating: float, expected: float, actual: float, k_factor: float) -> float:
    return rating + k_factor * (actual - expected)
