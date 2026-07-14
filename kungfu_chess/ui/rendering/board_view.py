"""`BoardView` -- thin coordinator, not a god object (plan section
7.2a). Owns no drawing logic of its own; just sequences its
collaborators. `overlay_renderer` is optional because it doesn't exist
until Phase 3 -- passing `None` simply skips that step, so Phase 1 can
use this exact class unchanged rather than a throwaway stand-in.
`panel_renderer` (Phase 5) is the same story: optional fourth
collaborator, skipped whenever either it or `panel_state` is None.
`toast_renderer` (optional fifth collaborator) draws last, on top of
everything else, and reads `game_over` straight off `snapshot` -- it
needs no separate state argument the way overlay/panel do, since that
flag is already part of the one thing every renderer is allowed to
see."""
from __future__ import annotations

from typing import Optional

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.board_renderer import BoardRenderer
from kungfu_chess.ui.rendering.piece_renderer import PieceRenderer
from kungfu_chess.view.game_snapshot import GameSnapshot


class BoardView:
    def __init__(self, board_renderer: BoardRenderer,
                 piece_renderer: PieceRenderer,
                 overlay_renderer: Optional[object] = None,
                 panel_renderer: Optional[object] = None,
                 toast_renderer: Optional[object] = None):
        self._board = board_renderer
        self._pieces = piece_renderer
        self._overlay = overlay_renderer
        self._panel = panel_renderer
        self._toast = toast_renderer

    def render(self, snapshot: GameSnapshot, input_state=None, panel_state=None) -> Img:
        frame = self._board.fresh_frame()
        self._pieces.draw(frame, snapshot)
        if self._overlay is not None:
            self._overlay.draw(frame, snapshot, input_state)
        if self._panel is not None and panel_state is not None:
            self._panel.draw(frame, panel_state)
        if self._toast is not None:
            self._toast.draw(frame, snapshot)
        return frame
