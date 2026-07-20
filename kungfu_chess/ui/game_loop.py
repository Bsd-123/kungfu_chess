"""Per-tick runtime driver (`run_loop`): wires `MouseRouter`, measures
wall-clock ticks, builds `InputState`/`PanelState`, and drives the
render/display/poll cycle each frame. All dependencies are injected."""
from __future__ import annotations

import time
from typing import Callable, Optional, Tuple

from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.controller import Controller
from kungfu_chess.network.network_client import NetworkClient
from kungfu_chess.network.network_sync import drain_network_client
from kungfu_chess.ui.composition import DEFAULT_PLAYER_NAMES
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.observers.moves_log_observer import MoveLogObserver
from kungfu_chess.ui.events.observers.score_observer import ScoreObserver
from kungfu_chess.ui.input.mouse_router import MouseRouter
from kungfu_chess.ui.layout import Layout
from kungfu_chess.ui.rendering.board_view import BoardView
from kungfu_chess.ui.rendering.overlay_renderer import InputState
from kungfu_chess.ui.rendering.panel_renderer import PanelState
from kungfu_chess.ui.rendering.renderer import Renderer


def run_loop(engine: GameEngine, controller: Controller, board_view: BoardView,
             renderer: Renderer, layout: Layout,
             move_log: Optional[MoveLogObserver] = None,
             score: Optional[ScoreObserver] = None,
             player_names: Tuple[str, str] = DEFAULT_PLAYER_NAMES,
             clock: Callable[[], float] = time.perf_counter,
             network_client: Optional[NetworkClient] = None,
             event_bus: Optional[EventBus] = None) -> None:
    """Real-time loop: advance engine clock by elapsed wall time (settling
    due motions synchronously), build `InputState`/`PanelState`, render,
    display, poll for quit. `move_log`/`score` are optional; omitting
    them skips the side panel. `network_client`/`event_bus` are Phase 2's
    networked-mode hook: when both are given, incoming server envelopes
    are drained and re-published onto `event_bus` once per frame before
    rendering (`engine` is then a `RemoteGameProxy`, whose
    `advance_clock` is a no-op -- the server is the authoritative
    clock); omitting them keeps local, single-process play unchanged."""
    mouse_router = MouseRouter(controller, board_offset=layout.piece_offset,
                                board_size=(layout.board_w, layout.board_h))
    renderer.register_mouse_handler(mouse_router.on_mouse_event)

    last = clock()
    running = True
    try:
        while running:
            now = clock()
            dt_ms = max(0, int((now - last) * 1000))
            last = now

            if network_client is not None and event_bus is not None:
                drain_network_client(network_client, engine, event_bus)

            engine.advance_clock(dt_ms)
            selected = controller.selected
            legal_destinations = (
                engine.legal_destinations(selected) if selected is not None else ()
            )
            input_state = InputState(
                selected=selected,
                cursor_pos=mouse_router.cursor_pos,
                last_click_pos=mouse_router.last_click_pos,
                legal_destinations=legal_destinations,
            )
            panel_state = None
            if move_log is not None or score is not None:
                white_moves = move_log.recent("w", 8) if move_log is not None else []
                black_moves = move_log.recent("b", 8) if move_log is not None else []
                panel_state = PanelState(
                    white_name=player_names[0],
                    black_name=player_names[1],
                    white_score=score.score["w"] if score is not None else 0,
                    black_score=score.score["b"] if score is not None else 0,
                    white_moves=white_moves,
                    black_moves=black_moves,
                )
            frame = board_view.render(engine.snapshot(), input_state, panel_state)
            renderer.draw_frame(frame)
            running = renderer.poll_events()
    finally:
        renderer.close()
