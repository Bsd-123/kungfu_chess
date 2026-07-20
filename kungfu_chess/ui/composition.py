"""UI composition root: the one place that constructs concrete renderer/
collaborator classes and wires them together (Composition Root pattern).

`build_session` boots the engine + controller. `build_board_view` builds
all rendering collaborators, returning `BoardView` + `Layout`.
`wire_event_observers` bridges the engine's `SettlementEvent`-based
listener hook into the UI's plain-value events (`MoveResolvedEvent`/
`JumpResolvedEvent`), so other UI modules never see engine/model types.

`ASSET_ROOT`: real piece art wins over the placeholder pack when present,
resolved once via `AssetPaths.resolve()`."""
from __future__ import annotations

import os
import time
from typing import Callable, Optional, Tuple

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.domain_event_wiring import wire_engine_domain_events
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.controller import Controller
from kungfu_chess.ui.setup import standard_start_rows
from kungfu_chess.ui.theme import DEFAULT_THEME, UITheme
from kungfu_chess.ui.asset_paths import DEFAULT_ASSET_PATHS
from kungfu_chess.ui.layout import BOARD_COLS, BOARD_ROWS, Layout
from kungfu_chess.ui.rendering.board_renderer import BoardRenderer
from kungfu_chess.ui.rendering.piece.renderer import PieceRenderer
from kungfu_chess.ui.rendering.overlay_renderer import OverlayRenderer
from kungfu_chess.ui.rendering.panel_renderer import PanelRenderer
from kungfu_chess.ui.rendering.toast_renderer import ToastRenderer
from kungfu_chess.ui.rendering.board_view import BoardView
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import (
    GameEndedEvent,
    GameStartedEvent,
    JumpResolvedEvent,
    MoveResolvedEvent,
)
from kungfu_chess.ui.events.observers.game_lifecycle_observer import GameLifecycleObserver
from kungfu_chess.ui.events.observers.moves_log_observer import MoveLogObserver
from kungfu_chess.ui.events.observers.score_observer import ScoreObserver
from kungfu_chess.ui.events.observers.sound_observer import SoundObserver

_UI_PACKAGE_DIR = os.path.dirname(__file__)
ASSET_ROOT, _ASSET_IS_REAL = DEFAULT_ASSET_PATHS.resolve(_UI_PACKAGE_DIR)
BOARD_BACKGROUND_PATH = os.path.join(ASSET_ROOT, "board.png")

# Shared default, used by both build_board_view (ToastRenderer) and
# game_loop.run_loop (PanelState).
DEFAULT_PLAYER_NAMES: Tuple[str, str] = ("White", "Black")


def build_session(config: GameConfig = None) -> Tuple[GameEngine, Controller]:
    """Boots one GameEngine + one Controller for the session, reusing
    the `build_game_engine` factory."""
    config = config or GameConfig()
    engine = build_game_engine(standard_start_rows, config)
    controller = Controller(engine, config.cell_pixel_size)
    return engine, controller


def wire_event_observers(
    engine: GameEngine,
    piece_renderer: Optional[PieceRenderer] = None,
    config: Optional[GameConfig] = None,
) -> Tuple[MoveLogObserver, ScoreObserver]:
    """Bridges GameEngine's settlement/lifecycle listeners into the UI's
    plain-value events, and wires every cross-cutting side effect (score,
    move log, sound, start/end animation triggers) through one `EventBus`
    instance. If `piece_renderer` is given, it's subscribed too so it can
    animate a slide-back correction on truncated landings. `config`
    supplies `ScoreObserver`'s piece values; omit to use its own default.
    Returns `(move_log, score)` -- the two observers `game_loop.run_loop`
    reads from each frame; `sound`/`lifecycle` are internal bus
    subscribers with no external readers yet."""
    event_bus = EventBus()
    move_log = MoveLogObserver(clock_ms_source=lambda: engine.clock_ms, event_bus=event_bus)
    score = ScoreObserver(piece_values=config.piece_values if config is not None else None,
                           event_bus=event_bus)
    sound = SoundObserver(event_bus)
    lifecycle = GameLifecycleObserver()

    event_bus.subscribe(MoveResolvedEvent, move_log.on_move_resolved)
    event_bus.subscribe(MoveResolvedEvent, score.on_move_resolved)
    event_bus.subscribe(JumpResolvedEvent, score.on_jump_resolved)
    event_bus.subscribe(MoveResolvedEvent, sound.on_move_resolved)
    event_bus.subscribe(JumpResolvedEvent, sound.on_jump_resolved)
    event_bus.subscribe(GameStartedEvent, sound.on_game_started)
    event_bus.subscribe(GameEndedEvent, sound.on_game_ended)
    event_bus.subscribe(GameStartedEvent, lifecycle.on_game_started)
    event_bus.subscribe(GameEndedEvent, lifecycle.on_game_ended)
    if piece_renderer is not None:
        event_bus.subscribe(MoveResolvedEvent, piece_renderer.on_move_resolved)

    wire_engine_domain_events(engine, event_bus)

    event_bus.publish(GameStartedEvent(timestamp_ms=engine.clock_ms))
    return move_log, score


def build_board_view(config: GameConfig = None,
                      clock: Callable[[], float] = time.perf_counter,
                      player_names: Tuple[str, str] = DEFAULT_PLAYER_NAMES,
                      theme: UITheme = DEFAULT_THEME,
                      ) -> Tuple[BoardView, Layout]:
    """Builds `BoardView` from `BoardRenderer`, `PieceRenderer`,
    `OverlayRenderer`, `PanelRenderer`, and `ToastRenderer`; optional
    collaborators no-op when their state argument is None. Returns
    `(board_view, layout)` -- callers also need `layout` to size the
    render window and build `MouseRouter`."""
    config = config or GameConfig()
    layout = Layout(config, theme)

    board_renderer = BoardRenderer(BOARD_BACKGROUND_PATH,
                                    cell_pixel_size=config.cell_pixel_size,
                                    cols=BOARD_COLS, rows=BOARD_ROWS,
                                    board_offset_x=layout.board_offset_x,
                                    board_offset_y=layout.board_offset_y,
                                    total_width=layout.total_width,
                                    total_height=layout.total_height,
                                    theme=theme.board)
    piece_renderer = PieceRenderer(ASSET_ROOT, config.cell_pixel_size, clock=clock,
                                    offset=layout.piece_offset, theme=theme.piece_animation,
                                    is_real=_ASSET_IS_REAL)
    overlay_renderer = OverlayRenderer(config.cell_pixel_size, offset=layout.piece_offset,
                                        clock=clock, theme=theme.overlay)
    panel_renderer = PanelRenderer(
        left_panel_x0=0, left_panel_width=layout.left_panel_width_px,
        right_panel_x0=layout.right_panel_x0, right_panel_width=layout.right_panel_width_px,
        panel_height=layout.total_height,
        board_x0=layout.board_offset_x, board_width=layout.board_image_w,
        top_band_y0=0, top_band_height=layout.top_band_height,
        bottom_band_y0=layout.bottom_band_y0, bottom_band_height=layout.bottom_band_height,
        theme=theme.panel,
    )
    toast_renderer = ToastRenderer(
        center_x=layout.board_offset_x + layout.board_image_w // 2,
        center_y=layout.board_offset_y + layout.board_image_h // 2,
        clock=clock,
        player_names=player_names,
        theme=theme.toast,
    )
    board_view = BoardView(board_renderer, piece_renderer, overlay_renderer,
                            panel_renderer, toast_renderer)
    return board_view, layout
