import pytest

from kungfu_chess.server.config import RoomConfig
from kungfu_chess.server.rooms.room_id_generator import generate_room_id

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def test_generated_id_has_the_configured_length():
    room_id = generate_room_id(existing_ids=set(), config=RoomConfig(room_code_length=5))
    assert len(room_id) == 5


def test_generated_id_only_uses_the_unambiguous_alphabet():
    room_id = generate_room_id(existing_ids=set(), config=RoomConfig(room_code_length=6))
    assert all(char in _ALPHABET for char in room_id)
    assert "0" not in room_id and "O" not in room_id
    assert "1" not in room_id and "I" not in room_id


def test_regenerates_on_collision_against_existing_ids():
    # First candidate collides, second doesn't -- both length 2 for a
    # short, deterministic script.
    scripted = iter(["A", "A", "B", "B"])
    choice_fn = lambda _alphabet: next(scripted)
    room_id = generate_room_id(existing_ids={"AA"}, config=RoomConfig(room_code_length=2),
                                choice_fn=choice_fn)
    assert room_id == "BB"


def test_raises_if_every_attempt_collides():
    choice_fn = lambda _alphabet: "A"
    with pytest.raises(RuntimeError):
        generate_room_id(existing_ids={"AA"}, config=RoomConfig(room_code_length=2),
                          choice_fn=choice_fn)


def test_ten_thousand_generated_ids_are_extremely_unlikely_to_collide():
    seen = set()
    for _ in range(10_000):
        seen.add(generate_room_id(existing_ids=seen, config=RoomConfig(room_code_length=5)))
    assert len(seen) == 10_000
