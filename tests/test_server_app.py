import asyncio
import json

import pytest
import websockets

from kungfu_chess.config import GameConfig
from kungfu_chess.server.app import KungFuChessServer, serve
from kungfu_chess.server.config import NetworkConfig, ServerConfig


async def _start_server(tick_interval_ms=50, game_config=None):
    # 127.0.0.1 rather than "localhost": avoids a slow getaddrinfo()
    # resolution on some platforms that would otherwise dominate every
    # test's runtime with a fresh event loop per test.
    network = NetworkConfig(host="127.0.0.1", port=0, tick_interval_ms=tick_interval_ms)
    config = ServerConfig(network=network, game=game_config or GameConfig())
    ws_server = await serve(config)
    port = ws_server.sockets[0].getsockname()[1]
    return ws_server, f"ws://127.0.0.1:{port}"


def _envelope(type_, payload, message_id="mid-1"):
    return json.dumps({
        "protocol_version": 1, "type": type_, "message_id": message_id,
        "timestamp_ms": 0, "payload": payload,
    })


async def test_first_two_connections_get_initial_snapshot():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            white_first = json.loads(await white.recv())
            black_first = json.loads(await black.recv())
            assert white_first["type"] == "snapshot"
            assert black_first["type"] == "snapshot"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_third_connection_is_rejected_and_closed():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await white.recv()  # snapshot
            await black.recv()  # snapshot
            await white.recv()  # game_started (broadcast once both have joined)
            await black.recv()  # game_started
            async with websockets.connect(url) as spectator:
                rejection = json.loads(await spectator.recv())
                assert rejection["type"] == "error"
                assert rejection["payload"]["reason"] == "session_full"
                with pytest.raises(websockets.exceptions.ConnectionClosed):
                    await spectator.recv()
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_white_can_move_own_piece():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await white.recv()  # snapshot
            await black.recv()  # snapshot
            await white.recv()  # game_started (broadcast once both have joined)
            await black.recv()  # game_started

            await white.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            response = json.loads(await white.recv())
            assert response["type"] == "move_response"
            assert response["payload"]["accepted"] is True
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_black_cannot_move_white_piece():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await white.recv()  # snapshot
            await black.recv()  # snapshot
            await white.recv()  # game_started (broadcast once both have joined)
            await black.recv()  # game_started

            await black.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            response = json.loads(await black.recv())
            assert response["type"] == "move_response"
            assert response["payload"]["accepted"] is False
            assert response["payload"]["reason"] == "wrong_color"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_malformed_frame_gets_error_response_without_closing_connection():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url):
            await white.recv()  # snapshot
            await white.recv()  # game_started

            await white.send("{not valid json")
            response = json.loads(await white.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "malformed_frame"

            # Connection must still be usable afterwards.
            await white.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }, message_id="after-malformed"))
            response = json.loads(await white.recv())
            assert response["type"] == "move_response"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_disconnect_frees_the_player_slot():
    ws_server, url = await _start_server()
    try:
        white = await websockets.connect(url)
        await white.recv()  # snapshot
        black = await websockets.connect(url)
        await black.recv()  # snapshot
        await white.recv()  # game_started
        await black.recv()  # game_started

        await white.close()
        # Give the server's connection handler a moment to observe the
        # close and run its cleanup (frees white's slot) before the
        # newcomer connects.
        await asyncio.sleep(0.05)

        async with websockets.connect(url) as newcomer:
            first = json.loads(await newcomer.recv())
            assert first["type"] == "snapshot"  # white's old slot was freed, not rejected

        await black.close()
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_both_players_leaving_clears_the_session_for_a_fresh_pair():
    ws_server, url = await _start_server()
    try:
        white = await websockets.connect(url)
        await white.recv()  # snapshot
        black = await websockets.connect(url)
        await black.recv()  # snapshot
        await white.recv()  # game_started
        await black.recv()  # game_started

        await white.close()
        await black.close()
        await asyncio.sleep(0.05)  # let the server observe both closes

        async with websockets.connect(url) as new_white, websockets.connect(url) as new_black:
            new_white_first = json.loads(await new_white.recv())
            new_black_first = json.loads(await new_black.recv())
            assert new_white_first["type"] == "snapshot"
            assert new_black_first["type"] == "snapshot"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_jump_request_is_handled_over_the_wire():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await white.recv()  # snapshot
            await black.recv()  # snapshot
            await white.recv()  # game_started
            await black.recv()  # game_started

            await white.send(_envelope("jump_request", {"row": 6, "col": 0}))
            response = json.loads(await white.recv())
            assert response["type"] == "jump_response"
            assert response["payload"]["accepted"] is True
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_unknown_message_type_gets_error_response():
    ws_server, url = await _start_server()
    try:
        async with websockets.connect(url) as white, websockets.connect(url):
            await white.recv()  # snapshot
            await white.recv()  # game_started

            await white.send(_envelope("not_a_real_type", {}))
            response = json.loads(await white.recv())
            assert response["type"] == "error"
            assert response["payload"]["reason"] == "unknown_type"
    finally:
        ws_server.close()
        await ws_server.wait_closed()


async def test_message_from_unregistered_connection_is_dropped_not_raised():
    # A message arriving before add_player has registered the connection
    # (or after it's been removed) must be silently dropped, not crash
    # the connection handler for other clients.
    server = KungFuChessServer(ServerConfig(network=NetworkConfig(host="127.0.0.1", port=0)))

    class FakeWebsocket:
        async def send(self, data):
            raise AssertionError("should never send a response for an unregistered connection")

    await server._handle_message(FakeWebsocket(), json.dumps({
        "protocol_version": 1, "type": "move_request", "message_id": "x",
        "timestamp_ms": 0, "payload": {},
    }))  # should not raise


async def test_real_move_settling_broadcasts_move_resolved_to_both_players():
    # Regression test: an actual settled move (via the tick loop's
    # engine.advance_clock, not a manually-published test event) must
    # reach both connections as a real move_resolved broadcast.
    ws_server, url = await _start_server(
        tick_interval_ms=10,
        game_config=GameConfig(move_duration_ms={'P': 20}, default_move_duration_ms=20))
    try:
        async with websockets.connect(url) as white, websockets.connect(url) as black:
            await white.recv()  # snapshot
            await black.recv()  # snapshot
            await white.recv()  # game_started
            await black.recv()  # game_started

            await white.send(_envelope("move_request", {
                "src_row": 6, "src_col": 0, "dst_row": 5, "dst_col": 0,
            }))
            move_response = json.loads(await white.recv())
            assert move_response["type"] == "move_response"
            assert move_response["payload"]["accepted"] is True

            # The move settles on the next tick; both connections should
            # receive a real move_resolved broadcast (relayed via
            # NetworkEventBusAdapter from the engine's own settlement,
            # not a snapshot).
            white_next = json.loads(await white.recv())
            black_next = json.loads(await black.recv())
            assert white_next["type"] in ("move_resolved", "snapshot")
            assert black_next["type"] in ("move_resolved", "snapshot")

            # Drain a couple more messages from each side to find the
            # move_resolved broadcast even if a snapshot interleaves.
            found_on_white = white_next["type"] == "move_resolved"
            found_on_black = black_next["type"] == "move_resolved"
            for _ in range(5):
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
        async with websockets.connect(url) as white, websockets.connect(url):
            await white.recv()  # snapshot
            await white.recv()  # game_started

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
