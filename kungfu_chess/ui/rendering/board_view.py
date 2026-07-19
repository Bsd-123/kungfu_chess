"""`BoardView` sequences board/piece/overlay/panel/toast rendering.
`overlay_renderer`/`panel_renderer` are optional (`None` skips that
step; `panel_renderer` also needs `panel_state`); `toast_renderer`
draws last, on top of everything."""
from __future__ import annotations

from typing import Optional

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.board_renderer import BoardRenderer
from kungfu_chess.ui.rendering.piece.renderer import PieceRenderer
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

    @property
    def piece_renderer(self) -> PieceRenderer:
        """Exposed so `ui/app.py` can wire `PieceRenderer` into the
        settlement-event pipeline."""
        return self._pieces

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
