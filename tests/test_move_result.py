import pytest
from dataclasses import FrozenInstanceError

from kungfu_chess.engine.move_result import MoveResult


def test_truthy_when_accepted():
    assert bool(MoveResult(True, 'ok')) is True


def test_falsy_when_rejected():
    assert bool(MoveResult(False, 'game_over')) is False


def test_fields():
    r = MoveResult(True, 'ok')
    assert r.is_accepted is True
    assert r.reason == 'ok'


def test_frozen():
    r = MoveResult(True, 'ok')
    with pytest.raises(FrozenInstanceError):
        r.is_accepted = False
