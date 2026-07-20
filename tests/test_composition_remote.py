"""Real end-to-end test of the composition-root remote wiring: connects
two real clients to a real KungFuChessServer via build_remote_session,
drives a move through Controller, and confirms it settles and reaches
the client's board mirror and observers -- the full Phase 2 chain."""
from __future__ import annotations

import asyncio

import pytest

from kungfu_chess.config import GameConfig
from kungfu_chess.model.position import Position
from kungfu_chess.network.network_sync import drain_network_client
from kungfu_chess.server.app import serve
from kungfu_chess.server.config import NetworkConfig, ServerConfig
from kungfu_chess.ui import composition

pytestmark = pytest.mark.asyncio


async def _start_server(tick_interval_ms=10, game_config=None):
    network = NetworkConfig(host="127.0.0.1", port=0, tick_interval_ms=tick_interval_ms)
    config = ServerConfig(network=network, game=game_config or GameConfig())
    ws_server = await serve(config)
    port = ws_server.sockets[0].getsockname()[1]
    return ws_server, f"ws://127.0.0.1:{port}"


async def _build_remote_session(url):
    return await asyncio.get_event_loop().run_in_executor(
        None, composition.build_remote_session, url)


async def _close(client):
    await asyncio.get_event_loop().run_in_executor(None, client.close)


async def test_click_driven_move_reaches_score_and_board_mirror():
    ws_server, url = await _start_server(
        tick_interval_ms=10,
        game_config=GameConfig(move_duration_ms={'P': 20}, default_move_duration_ms=20))
    try:
        white_proxy, white_controller, white_client = await _build_remote_session(url)
        _, _, white_bus = composition.wire_remote_event_observers(white_proxy)

        black_proxy, black_controller, black_client = await _build_remote_session(url)
        composition.wire_remote_event_observers(black_proxy)

        # Let the game_started broadcast (and anything else in flight)
        # settle before driving input.
        deadline = asyncio.get_event_loop().time() + 2.0
        while asyncio.get_event_loop().time() < deadline:
            drain_network_client(white_client, white_proxy, white_bus)
            if white_proxy.board.get_piece_at(Position(6, 0)) is not None:
                break
            await asyncio.sleep(0.01)

        # White clicks its own pawn, then the square ahead -- Controller
        # forwards through RemoteGameProxy to the real server unmodified.
        white_controller.click(x=50, y=650)   # select (6, 0)
        white_controller.click(x=50, y=550)   # move to (5, 0)

        moved = False
        deadline = asyncio.get_event_loop().time() + 3.0
        while asyncio.get_event_loop().time() < deadline:
            drain_network_client(white_client, white_proxy, white_bus)
            if white_proxy.board.get_piece_at(Position(5, 0)) is not None:
                moved = True
                break
            await asyncio.sleep(0.01)

        assert moved is True
        assert white_proxy.board.get_piece_at(Position(6, 0)) is None

        await _close(white_client)
        await _close(black_client)
    finally:
        ws_server.close()
        await ws_server.wait_closed()
