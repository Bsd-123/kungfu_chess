"""End-to-end tests against the real integrated server: authenticated
handshake (login/auth), lobby routing to matchmaking or rooms,
disconnect/reconnect, and room teardown -- all over real localhost
websockets, matching the Testing Strategy's "Protocol" and "Reconnect"
layers in master_work_plan.md."""
import asyncio
import json
import uuid

import pytest
import websockets

from kungfu_chess.config import GameConfig
from kungfu_chess.server.app import KungFuChessServer, serve
from kungfu_chess.server.config import (
    AuthenticationConfig, MatchmakingConfig, NetworkConfig, RoomConfig, ServerConfig,
)


def _server_config(tick_interval_ms=50, game_config=None, matchmaking_config=None, room_config=None):
    # 127.0.0.1 rather than "localhost": avoids a slow getaddrinfo()
    # resolution on some platforms. db_path=":memory:" gives every test
    # its own isolated, private auth database -- never the real
    # kungfu_chess.db file.
    return ServerConfig(
        network=NetworkConfig(host="127.0.0.1", port=0, tick_interval_ms=tick_interval_ms),
        game=game_config or GameConfig(),
        authentication=AuthenticationConfig(pbkdf2_iterations=1000, db_path=":memory:"),
        matchmaking=matchmaking_config or MatchmakingConfig(),
        room=room_config or RoomConfig(),
    )


async def _start_server(**kwargs):
    ws_server = await serve(_server_config(**kwargs))
    port = ws_server.sockets[0].getsockname()[1]
    return ws_server, f"ws://127.0.0.1:{port}"


def _envelope(type_, payload, message_id=None):
    # A fresh id per call by default (mirroring the real protocol's
    # new_message_id()) -- IdempotencyCache is keyed by message_id alone
    # and shared across the whole server, so two different connections'
    # requests sharing a hardcoded default id would collide and the
    # second would silently replay the first's cached response.
    return json.dumps({
        "protocol_version": 1, "type": type_, "message_id": message_id or uuid.uuid4().hex,
        "timestamp_ms": 0, "payload": payload,
    })


async def _login(ws, username, password="hunter2"):
    await ws.send(_envelope("login", {"username": username, "password": password}))
    response = json.loads(await ws.recv())
    assert response["type"] == "auth_response"
    assert response["payload"]["accepted"] is True
    return response["payload"]["session_token"]


async def _auth(ws, token):
    await ws.send(_envelope("auth", {"session_token": token}))
    return json.loads(await ws.recv())


async def _play_request(ws, message_id=None):
    await ws.send(_envelope("play_request", {}, message_id))
    return json.loads(await ws.recv())


async def _create_room(ws):
    await ws.send(_envelope("create_room", {}))
    response = json.loads(await ws.recv())
    assert response["type"] == "room_created"
    return response["payload"]["room_id"]


async def _join_room(ws, room_id):
    await ws.send(_envelope("join_room", {"room_id": room_id}))
    return json.loads(await ws.recv())


async def _match_players(white, black):
    """Sends play_request from both (already-authenticated) connections
    and drains the resulting match_found -> snapshot -> game_started
    sequence for each -- guaranteed in that order per connection by
    KungFuChessServer._start_matched_game. Returns the shared game_id."""
    await _play_request(white)
    await _play_request(black)

    white_match = json.loads(await white.recv())
    black_match = json.loads(await black.recv())
    assert white_match["type"] == "match_found"
    assert white_match["payload"]["role"] == "white"
    assert black_match["type"] == "match_found"
    assert black_match["payload"]["role"] == "black"
    assert white_match["payload"]["game_id"] == black_match["payload"]["game_id"]

    assert json.loads(await white.recv())["type"] == "snapshot"
    assert json.loads(await black.recv())["type"] == "snapshot"
    assert json.loads(await white.recv())["type"] == "game_started"
    assert json.loads(await black.recv())["type"] == "game_started"

    return white_match["payload"]["game_id"]


# -- authentication -----------------------------------------------------

async def test_login_with_a_new_username_registers_and_returns_a_token():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            token = await _login(ws, "alice")
            assert token
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_login_with_wrong_password_for_a_known_username_is_rejected():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as first:
            await _login(first, "alice", "hunter2")
        async with websockets.connect(url) as second:
            await second.send(_envelope("login", {"username": "alice", "password": "wrong"}))
            response = json.loads(await second.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "invalid_credentials"
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                await second.recv()
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_login_missing_password_is_rejected():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_envelope("login", {"username": "alice"}))
            response = json.loads(await ws.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "missing_credentials"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_auth_with_a_valid_token_is_accepted_not_reconnected():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as first:
            token = await _login(first, "alice")
        async with websockets.connect(url) as second:
            response = await _auth(second, token)
            assert response["payload"] == {"accepted": True, "reconnected": False}
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_auth_with_an_invalid_token_is_rejected_and_closed():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_envelope("auth", {"session_token": "not-a-real-token"}))
            response = json.loads(await ws.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "invalid_session_token"
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                await ws.recv()
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_first_message_that_is_not_login_or_auth_is_rejected():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_envelope("play_request", {}))
            response = json.loads(await ws.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "auth_required"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


# -- matchmaking ("Play") -------------------------------------------------

async def test_two_play_requests_are_matched_and_receive_match_found_and_snapshot():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await _login(white, "alice")
            await _login(black, "bob")
            await _match_players(white, black)
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_matched_players_can_move_and_wrong_color_is_rejected():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await _login(white, "alice")
            await _login(black, "bob")
            await _match_players(white, black)

            await black.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            rejected = json.loads(await black.recv())
            assert rejected["payload"]["accepted"] is False
            assert rejected["payload"]["reason"] == "wrong_color"

            await white.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            accepted = json.loads(await white.recv())
            assert accepted["payload"]["accepted"] is True
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_play_request_while_already_queued_is_rejected():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await _login(ws, "alice")
            await _play_request(ws)
            second = await _play_request(ws)
            assert second["type"] == "error"
            assert second["payload"]["reason"] == "already_queued"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_matchmaking_timeout_notifies_the_waiting_player():
    ws_server, url = await _start_server(matchmaking_config=MatchmakingConfig(timeout_s=0.03))
    try:
        async with websockets.connect(url) as ws:
            await _login(ws, "alice")
            await _play_request(ws)
            timeout_message = json.loads(await ws.recv())
            assert timeout_message["type"] == "matchmaking_timed_out"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


# -- rooms ----------------------------------------------------------------

async def test_create_room_seats_the_creator_as_white_and_sends_a_snapshot():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await _login(ws, "alice")
            room_id = await _create_room(ws)
            assert len(room_id) == RoomConfig().room_code_length
            snapshot = json.loads(await ws.recv())
            assert snapshot["type"] == "snapshot"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_join_room_seats_the_second_connection_as_black_and_starts_the_game():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as creator, websockets.connect(url) as joiner:
            await _login(creator, "alice")
            await _login(joiner, "bob")
            room_id = await _create_room(creator)
            await creator.recv()  # snapshot

            joined = await _join_room(joiner, room_id)
            assert joined["type"] == "room_joined"
            assert joined["payload"]["role"] == "black"
            await joiner.recv()  # snapshot
            joiner_game_started = json.loads(await joiner.recv())
            assert joiner_game_started["type"] == "game_started"

            creator_game_started = json.loads(await creator.recv())
            assert creator_game_started["type"] == "game_started"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_join_room_with_unknown_id_is_rejected():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await _login(ws, "alice")
            response = await _join_room(ws, "NOPE1")
            assert response["type"] == "room_join_rejected"
            assert response["payload"]["reason"] == "room_not_found"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_third_joiner_becomes_a_spectator_and_cannot_move():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as creator, websockets.connect(url) as joiner, \
                websockets.connect(url) as spectator:
            await _login(creator, "alice")
            await _login(joiner, "bob")
            await _login(spectator, "carol")

            room_id = await _create_room(creator)
            await creator.recv()  # snapshot
            await _join_room(joiner, room_id)
            await joiner.recv()  # snapshot
            await joiner.recv()  # game_started
            await creator.recv()  # game_started

            joined = await _join_room(spectator, room_id)
            assert joined["type"] == "room_joined"
            assert joined["payload"]["role"] is None
            await spectator.recv()  # snapshot

            await spectator.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            rejected = json.loads(await spectator.recv())
            assert rejected["payload"]["accepted"] is False
            assert rejected["payload"]["reason"] == "not_a_player"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_join_room_beyond_the_spectator_cap_is_rejected():
    ws_server, url = await _start_server(room_config=RoomConfig(spectator_cap=1))
    try:
        async with websockets.connect(url) as creator, websockets.connect(url) as joiner, \
                websockets.connect(url) as spectator_a, websockets.connect(url) as spectator_b:
            await _login(creator, "alice")
            await _login(joiner, "bob")
            await _login(spectator_a, "carol")
            await _login(spectator_b, "dave")

            room_id = await _create_room(creator)
            await creator.recv()  # snapshot
            await _join_room(joiner, room_id)
            await joiner.recv()  # snapshot
            await joiner.recv()  # game_started
            await creator.recv()  # game_started

            await _join_room(spectator_a, room_id)
            await spectator_a.recv()  # snapshot

            rejected = await _join_room(spectator_b, room_id)
            assert rejected["type"] == "room_join_rejected"
            assert rejected["payload"]["reason"] == "room_full"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_room_is_torn_down_once_both_players_have_left():
    ws_server, url = await _start_server()
    try:
        creator = await websockets.connect(url)
        await _login(creator, "alice")
        room_id = await _create_room(creator)
        await creator.recv()  # snapshot

        joiner = await websockets.connect(url)
        await _login(joiner, "bob")
        await _join_room(joiner, room_id)
        await joiner.recv()  # snapshot
        await joiner.recv()  # game_started
        await creator.recv()  # game_started

        await creator.close()
        await joiner.close()
        await asyncio.sleep(0.1)

        async with websockets.connect(url) as latecomer:
            await _login(latecomer, "carol")
            rejected = await _join_room(latecomer, room_id)
            assert rejected["type"] == "room_join_rejected"
            assert rejected["payload"]["reason"] == "room_not_found"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


# -- disconnect / reconnect (Decision 7) -----------------------------------

async def test_disconnect_sends_a_single_player_disconnected_message_to_the_opponent():
    ws_server, url = await _start_server()
    try:
        white = await websockets.connect(url)
        await _login(white, "alice")
        black = await websockets.connect(url)
        await _login(black, "bob")
        await _match_players(white, black)

        await white.close()
        disconnect_message = json.loads(await black.recv())
        assert disconnect_message["type"] == "player_disconnected"
        assert disconnect_message["payload"]["role"] == "white"
        assert disconnect_message["payload"]["grace_period_ms"] > 0

        await black.close()
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_reconnecting_within_the_grace_period_resumes_the_same_game():
    ws_server, url = await _start_server()
    try:
        white = await websockets.connect(url)
        white_token = await _login(white, "alice")
        black = await websockets.connect(url)
        await _login(black, "bob")
        game_id = await _match_players(white, black)

        await white.close()
        await black.recv()  # player_disconnected

        async with websockets.connect(url) as reconnected:
            response = await _auth(reconnected, white_token)
            assert response["payload"]["accepted"] is True
            assert response["payload"]["reconnected"] is True
            assert response["payload"]["role"] == "white"
            assert response["payload"]["game_id"] == game_id

            snapshot = json.loads(await reconnected.recv())
            assert snapshot["type"] == "snapshot"

            # The reconnected socket can play immediately.
            await reconnected.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            move_response = json.loads(await reconnected.recv())
            assert move_response["payload"]["accepted"] is True

        await black.close()
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_reconnect_broadcasts_reconnected_to_the_opponent():
    ws_server, url = await _start_server()
    try:
        white = await websockets.connect(url)
        white_token = await _login(white, "alice")
        black = await websockets.connect(url)
        await _login(black, "bob")
        await _match_players(white, black)

        await white.close()
        await black.recv()  # player_disconnected

        async with websockets.connect(url) as reconnected:
            await _auth(reconnected, white_token)
            reconnected_message = json.loads(await black.recv())
            assert reconnected_message["type"] == "reconnected"
            assert reconnected_message["payload"]["role"] == "white"

        await black.close()
    finally:
        ws_server.close()
        await ws_server.wait_closed()


# -- protocol edge cases (mostly unchanged from Phase 2) -------------------

async def test_malformed_frame_gets_error_response_without_closing_connection():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await _login(ws, "alice")
            await ws.send("{not valid json")
            response = json.loads(await ws.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "malformed_frame"

            # Connection must still be usable afterwards.
            still_works = await _play_request(ws)
            assert still_works["type"] == "play_request_accepted"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_unknown_message_type_from_a_seated_player_gets_error_response():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await _login(white, "alice")
            await _login(black, "bob")
            await _match_players(white, black)

            await white.send(_envelope("not_a_real_type", {}))
            response = json.loads(await white.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "unknown_type"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_unknown_message_type_from_a_lobby_connection_gets_error_response():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as ws:
            await _login(ws, "alice")
            await ws.send(_envelope("not_a_real_type", {}))
            response = json.loads(await ws.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "unknown_type"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_jump_request_is_handled_over_the_wire():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await _login(white, "alice")
            await _login(black, "bob")
            await _match_players(white, black)

            await white.send(_envelope("jump_request", {"row": 6, "col": 0}))
            response = json.loads(await white.recv())
            assert response["type"] == "jump_response"
            assert response["payload"]["accepted"] is True
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_real_move_settling_broadcasts_move_resolved_to_both_players():
    ws_server, url = await _start_server(
        tick_interval_ms=10,
        game_config=GameConfig(move_duration_ms={'P': 20}, default_move_duration_ms=20))
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await _login(white, "alice")
            await _login(black, "bob")
            await _match_players(white, black)

            await white.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            move_response = json.loads(await white.recv())
            assert move_response["type"] == "move_response"
            assert move_response["payload"]["accepted"] is True

            found_on_white = False
            found_on_black = False
            for _ in range(8):
                if found_on_white and found_on_black:
                    break
                if not found_on_white:
                    msg = json.loads(await white.recv())
                    found_on_white = msg["type"] == "move_resolved"
                if not found_on_black:
                    msg = json.loads(await black.recv())
                    found_on_black = msg["type"] == "move_resolved"
            assert found_on_white
            assert found_on_black
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_duplicate_message_id_replays_cached_response():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await _login(white, "alice")
            await _login(black, "bob")
            await _match_players(white, black)

            request = _envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }, message_id="dup-1")
            await white.send(request)
            first = json.loads(await white.recv())
            assert first["payload"]["accepted"] is True

            # Retry with the same message_id -- must replay the same
            # response instead of reprocessing (which would now fail
            # with motion_in_progress since the piece is already moving).
            await white.send(request)
            second = json.loads(await white.recv())
            assert second["payload"] == first["payload"]
            assert second["message_id"] == first["message_id"]
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_message_from_a_lobby_connection_with_no_registered_session_does_not_crash():
    # A move/jump request from a connection that never got seated in any
    # GameSession must be rejected cleanly (routed to the lobby handler,
    # which returns "unknown_type"), never crash the connection handler
    # for other clients.
    server = KungFuChessServer(_server_config())

    class FakeWebsocket:
        def __init__(self):
            self.sent = []

        async def send(self, data):
            self.sent.append(data)

    fake = FakeWebsocket()
    await server._handle_message(fake, json.dumps({
        "protocol_version": 1, "type": "move_request", "message_id": "x",
        "timestamp_ms": 0, "payload": {},
    }), user_id=1)

    assert len(fake.sent) == 1
    response = json.loads(fake.sent[0])
    assert response["payload"]["reason"] == "unknown_type"
