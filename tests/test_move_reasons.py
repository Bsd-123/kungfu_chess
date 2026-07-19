from kungfu_chess.engine.move_reasons import MoveReasons


def test_reason_constants():
    assert MoveReasons.OK == 'ok'
    assert MoveReasons.GAME_OVER == 'game_over'
    assert MoveReasons.MOTION_IN_PROGRESS == 'motion_in_progress'
    assert MoveReasons.COOLDOWN == 'cooldown'
