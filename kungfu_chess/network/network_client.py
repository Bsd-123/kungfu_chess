"""Client-side WebSocket transport adapter. Runs its own asyncio event
loop on a background thread so the UI's synchronous render loop
(`ui/game_loop.py::run_loop`) never blocks on network I/O.

Outgoing commands are fire-and-forget: `Controller` already discards
`request_move`/`request_jump`'s return value in the local, single-
process mode (the server is authoritative; acceptance/rejection comes
back later as a message, not a synchronous return value). Incoming
envelopes land on a thread-safe queue that `poll_incoming()` drains
once per rendered frame."""
from __future__ import annotations

import asyncio
import queue
import threading
from typing import List, Optional

import websockets

from kungfu_chess.model.position import Position
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.protocol import Envelope, make_envelope


class NetworkClient:
    def __init__(self, url: str, network_config: Optional[NetworkConfig] = None):
        self._url = url
        self._config = network_config or NetworkConfig()
        self._incoming: "queue.Queue[Envelope]" = queue.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._websocket = None
        self._stop_event: Optional[asyncio.Event] = None
        self._connected = threading.Event()
        self._connect_error: Optional[BaseException] = None

    def connect(self, timeout: float = 5.0) -> None:
        """Starts the background event-loop thread and blocks until the
        connection is established. Raises the connection error (or
        TimeoutError if nothing happened within `timeout`) on failure."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._connected.wait(timeout):
            raise TimeoutError(f"could not connect to {self._url} within {timeout}s")
        if self._connect_error is not None:
            raise self._connect_error

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    async def _main(self) -> None:
        self._stop_event = asyncio.Event()
        try:
            async with websockets.connect(self._url) as websocket:
                self._websocket = websocket
                self._connected.set()
                receive_task = asyncio.ensure_future(self._receive_loop(websocket))
                stop_task = asyncio.ensure_future(self._stop_event.wait())
                await asyncio.wait([receive_task, stop_task],
                                    return_when=asyncio.FIRST_COMPLETED)
                receive_task.cancel()
                stop_task.cancel()
        except Exception as exc:  # connection refused, DNS failure, etc.
            self._connect_error = exc
            self._connected.set()

    async def _receive_loop(self, websocket) -> None:
        try:
            async for raw in websocket:
                envelope = Envelope.from_json(raw, self._config)
                self._incoming.put(envelope)
        except websockets.exceptions.ConnectionClosed:
            pass

    def _send(self, type_: str, payload: dict) -> None:
        envelope = make_envelope(type_, payload, self._config)
        asyncio.run_coroutine_threadsafe(self._websocket.send(envelope.to_json()), self._loop)

    def request_move(self, source: Position, destination: Position) -> None:
        self._send("move_request", {
            "src_row": source.row, "src_col": source.col,
            "dst_row": destination.row, "dst_col": destination.col,
        })

    def request_jump(self, position: Position) -> None:
        self._send("jump_request", {"row": position.row, "col": position.col})

    def poll_incoming(self) -> List[Envelope]:
        """Non-blocking drain of every envelope received since the last call."""
        drained: List[Envelope] = []
        while True:
            try:
                drained.append(self._incoming.get_nowait())
            except queue.Empty:
                break
        return drained

    def close(self, timeout: float = 2.0) -> None:
        if self._loop is not None and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
