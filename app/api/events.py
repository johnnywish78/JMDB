"""EventBus → WebSocket bridge.

Subscribes once to the existing domain EventBus and fans every event out to
connected WebSocket clients as JSON. No second event architecture: the
mapping is a rename layer only.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import queue

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# domain event class name -> wire type
EVENT_NAMES = {
    "LibraryScanStarted": "scan_started",
    "LibraryScanProgress": "scan_progress",
    "LibraryScanFinished": "scan_finished",
    "MediaAdded": "library_changed",
    "MediaUpdated": "library_changed",
    "MediaRemoved": "library_changed",
    "MetadataUpdated": "metadata_updated",
    "MetadataBatchFinished": "metadata_updated",
    "ArtworkUpdated": "metadata_updated",
    "PlaybackStarted": "playback_started",
    "PlaybackProgress": "playback_progress",
    "PlaybackStopped": "playback_stopped",
    "PlaybackFinished": "playback_finished",
    "ThemeChanged": "theme_changed",
    "SettingsChanged": "settings_changed",
    "ToastRequested": "toast",
}


class EventBridge:
    """Thread-safe fan-out from the sync EventBus to async websockets."""

    def __init__(self, events_bus) -> None:
        self._queue: "queue.Queue[dict | None]" = queue.Queue(maxsize=1000)
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        events_bus.subscribe(object, self._on_event)

    def _on_event(self, event) -> None:
        """Called from arbitrary threads (scan thread, playback, ...)."""
        name = type(event).__name__
        wire = EVENT_NAMES.get(name)
        if wire is None:
            return
        try:
            data = dataclasses.asdict(event)
        except TypeError:
            data = {"repr": repr(event)}
        try:
            self._queue.put_nowait({"type": wire, "data": data})
        except queue.Full:  # pragma: no cover - slow client
            pass

    # -- async side ----------------------------------------------------------
    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._task = asyncio.get_event_loop().create_task(self._pump())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _pump(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            # Poll with a timeout: a bare blocking queue.get() inside the
            # executor can never be interrupted by task cancellation, which
            # would hang application shutdown.
            try:
                item = await loop.run_in_executor(
                    None, self._queue.get, True, 0.2
                )
            except queue.Empty:
                continue
            if item is None:
                break
            dead = []
            for socket in list(self._clients):
                try:
                    # default=str keeps datetimes and other non-JSON fields
                    # from killing the pump
                    await socket.send_text(json.dumps(item, default=str))
                except Exception:
                    dead.append(socket)
            for socket in dead:
                self._clients.discard(socket)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        try:
            while True:
                # client pings keep the socket alive; content is ignored
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            self._clients.discard(websocket)
