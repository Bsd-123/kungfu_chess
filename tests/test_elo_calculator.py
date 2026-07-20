import pytest

from kungfu_chess.server.rating.elo_calculator import expected_score, update_rating


def test_expected_score_is_half_for_equal_ratings():
    assert expected_score(1200, 1200) == pytest.approx(0.5)


def test_expected_score_favors_the_higher_rated_player():
    assert expected_score(1400, 1200) > 0.5
    assert expected_score(1200, 1400) < 0.5


def test_expected_scores_for_both_players_sum_to_one():
    a = expected_score(1350, 1180)
    b = expected_score(1180, 1350)
    assert a + b == pytest.approx(1.0)


def test_update_rating_raises_on_a_win():
    new_rating = update_rating(1200, expected=0.5, actual=1.0, k_factor=32)
    assert new_rating == pytest.approx(1216.0)


def test_update_rating_lowers_on_a_loss():
    new_rating = update_rating(1200, expected=0.5, actual=0.0, k_factor=32)
    assert new_rating == pytest.approx(1184.0)


def test_update_rating_is_unchanged_when_result_matches_expectation_exactly():
    new_rating = update_rating(1200, expected=1.0, actual=1.0, k_factor=32)
    assert new_rating == pytest.approx(1200.0)


def test_a_win_against_a_stronger_opponent_gains_more_than_against_a_weaker_one():
    gain_vs_stronger = update_rating(1200, expected_score(1200, 1400), 1.0, 32) - 1200
    gain_vs_weaker = update_rating(1200, expected_score(1200, 1000), 1.0, 32) - 1200
    assert gain_vs_stronger > gain_vs_weaker
