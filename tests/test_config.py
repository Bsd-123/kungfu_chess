from kungfu_chess.config import GameConfig


def test_defaults_current_behavior():
    config = GameConfig()
    assert config.cell_pixel_size == 100
    assert config.jump_duration_ms == 2500
    assert config.default_move_duration_ms == 2500
    assert config.empty_token == '.'
    assert config.board_marker == 'Board:'
    assert config.commands_marker == 'Commands:'
    assert config.print_board_command == 'print board'
    assert config.move_duration_ms == {}
    assert config.win_condition_piece_types == ('K',)


def test_move_duration_ms_default_factory_independent_per_instance():
    c1 = GameConfig()
    c2 = GameConfig()
    assert c1.move_duration_ms is not c2.move_duration_ms
    c1.move_duration_ms['P'] = 500
    assert 'P' not in c2.move_duration_ms


def test_cooldown_dicts_independent_per_instance():
    c1 = GameConfig()
    c2 = GameConfig()
    assert c1.cooldown_ms is not c2.cooldown_ms
    assert c1.jump_cooldown_ms is not c2.jump_cooldown_ms


def test_move_duration_for_uses_default_when_absent():
    config = GameConfig()
    assert config.move_duration_for('P') == config.default_move_duration_ms


def test_move_duration_for_uses_override():
    config = GameConfig(move_duration_ms={'N': 111})
    assert config.move_duration_for('N') == 111
    assert config.move_duration_for('P') == config.default_move_duration_ms


def test_cooldown_for_uses_default_when_absent():
    config = GameConfig()
    assert config.cooldown_for('P') == config.default_cooldown_ms


def test_cooldown_for_uses_override():
    config = GameConfig(cooldown_ms={'K': 42})
    assert config.cooldown_for('K') == 42


def test_jump_cooldown_for_uses_default_when_absent():
    config = GameConfig()
    assert config.jump_cooldown_for('P') == config.default_jump_cooldown_ms


def test_jump_cooldown_for_uses_override():
    config = GameConfig(jump_cooldown_ms={'K': 7})
    assert config.jump_cooldown_for('K') == 7


def test_token_pattern_matches_empty_and_piece_tokens():
    import re
    pattern = re.compile(GameConfig().token_pattern)
    assert pattern.match('.')
    assert pattern.match('wK')
    assert pattern.match('bP')
    assert not pattern.match('wX')
    assert not pattern.match('w')
    assert not pattern.match('wKK')


def test_frozen_dataclass_is_immutable():
    import pytest
    from dataclasses import FrozenInstanceError
    config = GameConfig()
    with pytest.raises(FrozenInstanceError):
        config.cell_pixel_size = 50


def test_motion_state_constants():
    assert GameConfig.MOTION_STATE_IDLE == 'idle'
    assert GameConfig.MOTION_STATE_MOVE == 'move'
    assert GameConfig.MOTION_STATE_JUMP == 'jump'


def test_piece_values_covers_every_token_pattern_piece_type():
    config = GameConfig()
    for piece_type in 'KQRBNP':
        assert piece_type in config.piece_values


def test_piece_values_independent_per_instance():
    c1 = GameConfig()
    c2 = GameConfig()
    assert c1.piece_values is not c2.piece_values
