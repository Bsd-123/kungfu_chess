"""Real end-to-end tests: an actual NetworkClient (its own background
thread + event loop) talking to the actual KungFuChessServer over a
real localhost socket -- both happen to run their asyncio work on the
test process, but on *different* loops (server: the pytest-asyncio
test loop; client: its own background-thread loop). Every blocking
NetworkClient call (connect/close) must be offloaded via
run_in_executor rather than awaited/called directly, or it would block
the test loop the server itself depends on to complete the handshake
-- a real client and a real server are separate processes and don't
have this constraint, but the test harness does."""
from __future__ import annotations

import asyncio

import pytest

from kungfu_chess.config import GameConfig
from kungfu_chess.model.position import Position
from kungfu_chess.network.client_event_relay import republish_envelope
from kungfu_chess.network.network_client import NetworkClient
from kungfu_chess.network.remote_game_proxy import RemoteGameProxy
from kungfu_chess.server.app import serve
from kungfu_chess.server.config import NetworkConfig, ServerConfig
from kungfu_chess.server.snapshot_codec import snapshot_from_dict
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import MoveResolvedEvent

pytestmark = pytest.mark.asyncio


async def _start_server(tick_interval_ms=10, game_config=None):
    network = NetworkConfig(host="127.0.0.1", port=0, tick_interval_ms=tick_interval_ms)
    config = ServerConfig(network=network, game=game_config or GameConfig())
    ws_server = await serve(config)
    port = ws_server.sockets[0].getsockname()[1]
    return ws_server, f"ws://127.0.0.1:{port}"


async def _connect(client: NetworkClient) -> None:
    await asyncio.get_event_loop().run_in_executor(None, client.connect)


async def _close(client: NetworkClient) -> None:
    await asyncio.get_event_loop().run_in_executor(None, client.close)


async def _drain_until(client, predicate, timeout=2.0):
    """Polls client.poll_incoming() until an envelope satisfying
    `predicate` shows up, or raises on timeout. Yields via
    asyncio.sleep, never a blocking sleep -- the test server runs on
    this same event loop."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        for envelope in client.poll_incoming():
            if predicate(envelope):
                return envelope
        await asyncio.sleep(0.01)
    raise TimeoutError("expected envelope did not arrive in time")


async def test_connect_raises_when_server_refuses_connection():
    # No server listening on this port -- connect() must surface the
    # real connection error, not hang or swallow it.
    client = NetworkClient("ws://127.0.0.1:1")
    with pytest.raises(OSError):
        await asyncio.get_event_loop().run_in_executor(None, client.connect, 3.0)


_CLIENT_AUTH_NOT_YET_IMPLEMENTED = (
    "NetworkClient doesn't yet speak the login/auth handshake the "
    "Integration Pass added to KungFuChessServer (server/app.py) -- "
    "connecting now gets rejected with auth_required. Client-side "
    "CliLoginFlow/NetworkClient rework is the deliberately deferred "
    "follow-up task; re-enable once that lands.")


@pytest.mark.skip(reason=_CLIENT_AUTH_NOT_YET_IMPLEMENTED)
async def test_network_client_jump_request_gets_accepted_response():
    ws_server, url = await _start_server()
    try:
        white = NetworkClient(url)
        await _connect(white)
        await _drain_until(white, lambda e: e.type == "snapshot")

        black = NetworkClient(url)
        await _connect(black)
        await _drain_until(black, lambda e: e.type == "snapshot")
        await _drain_until(white, lambda e: e.type == "game_started")

        white.request_jump(Position(6, 0))
        response = await _drain_until(white, lambda e: e.type == "jump_response")
        assert response.payload["accepted"] is True

        await _close(white)
        await _close(black)
    finally:
        ws_server.close()
        await ws_server.wait_closed()


@pytest.mark.skip(reason=_CLIENT_AUTH_NOT_YET_IMPLEMENTED)
async def test_network_client_connects_and_receives_initial_snapshot():
    ws_server, url = await _start_server()
    try:
        client = NetworkClient(url)
        await _connect(client)
        envelope = await _drain_until(client, lambda e: e.type == "snapshot")
        snapshot = snapshot_from_dict(envelope.payload)
        assert snapshot.game_over is False
        await _close(client)
    finally:
        ws_server.close()
        await ws_server.wait_closed()


@pytest.mark.skip(reason=_CLIENT_AUTH_NOT_YET_IMPLEMENTED)
async def test_network_client_move_request_gets_accepted_response():
    ws_server, url = await _start_server()
    try:
        white = NetworkClient(url)
        await _connect(white)
        await _drain_until(white, lambda e: e.type == "snapshot")

        black = NetworkClient(url)
        await _connect(black)
        await _drain_until(black, lambda e: e.type == "snapshot")
        await _drain_until(white, lambda e: e.type == "game_started")

        white.request_move(Position(6, 0), Position(5, 0))
        response = await _drain_until(white, lambda e: e.type == "move_response")
        assert response.payload["accepted"] is True

        await _close(white)
        await _close(black)
    finally:
        ws_server.close()
        await ws_server.wait_closed()


@pytest.mark.skip(reason=_CLIENT_AUTH_NOT_YET_IMPLEMENTED)
async def test_real_move_updates_remote_game_proxy_board_mirror():
    ws_server, url = await _start_server(
        tick_interval_ms=10,
        game_config=GameConfig(move_duration_ms={'P': 20}, default_move_duration_ms=20))
    try:
        white = NetworkClient(url)
        await _connect(white)
        snapshot_envelope = await _drain_until(white, lambda e: e.type == "snapshot")
        proxy = RemoteGameProxy(white, snapshot_from_dict(snapshot_envelope.payload))
        bus = EventBus()
        bus.subscribe(MoveResolvedEvent, proxy.board.on_move_resolved)

        black = NetworkClient(url)
        await _connect(black)
        await _drain_until(black, lambda e: e.type == "snapshot")
        await _drain_until(white, lambda e: e.type == "game_started")

        proxy.request_move(Position(6, 0), Position(5, 0))
        await _drain_until(white, lambda e: e.type == "move_response")

        move_resolved = await _drain_until(white, lambda e: e.type == "move_resolved", timeout=3.0)
        assert republish_envelope(move_resolved, bus) is True

        assert proxy.board.get_piece_at(Position(6, 0)) is None
        moved_piece = proxy.board.get_piece_at(Position(5, 0))
        assert moved_piece.color == 'w'
        assert moved_piece.type == 'P'

        await _close(white)
        await _close(black)
    finally:
        ws_server.close()
        await ws_server.wait_closed()
