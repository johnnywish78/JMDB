"""Synchronous in-process event bus. Qt-free so services stay testable;
UI layers bridge it to Qt signals where needed."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

# event names
LIBRARY_CHANGED = "library.changed"
SETTINGS_CHANGED = "settings.changed"
PLAYBACK_STARTED = "playback.started"
PLAYBACK_FINISHED = "playback.finished"
PLAYBACK_STOPPED = "playback.stopped"
MEDIA_STATE_CHANGED = "media.state_changed"  # favorites/watchlist/watched toggles


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable[..., None]) -> None:
        self._subs[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., None]) -> None:
        if callback in self._subs.get(event, []):
            self._subs[event].remove(callback)

    def emit(self, event: str, **payload: Any) -> None:
        for callback in list(self._subs.get(event, [])):
            try:
                callback(**payload)
            except Exception:  # a broken subscriber must never break emitters
                import logging

                logging.getLogger("jmdb.bus").exception("subscriber failed for %s", event)
