"""Application events and a thread-safe event bus.

Events decouple subsystems (scanner, metadata, playback, settings, UI):
producers publish, consumers subscribe. The bus is pure Python so non-Qt
subsystems (scanner, providers) can use it; a Qt bridge in the UI layer
marshals events onto the GUI thread.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Base class for all application events."""

    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class LibraryScanStarted(Event):
    location_id: int | None = None  # None = all locations
    total_locations: int = 0


@dataclass(frozen=True)
class LibraryScanProgress(Event):
    location_id: int | None = None
    current_path: str = ""
    files_seen: int = 0
    files_indexed: int = 0
    current: int = 0
    total: int = 0
    paused: bool = False


@dataclass(frozen=True)
class LibraryScanFinished(Event):
    location_id: int | None = None
    status: str = "completed"
    files_seen: int = 0
    files_indexed: int = 0
    files_missing: int = 0
    files_added: int = 0
    files_removed: int = 0
    movies_added: int = 0
    shows_added: int = 0
    episodes_added: int = 0
    artists_added: int = 0
    albums_added: int = 0
    tracks_added: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class MediaAdded(Event):
    media_type: str = ""
    media_id: int = 0


@dataclass(frozen=True)
class MediaUpdated(Event):
    media_type: str = ""
    media_id: int = 0


@dataclass(frozen=True)
class MediaRemoved(Event):
    media_type: str = ""
    media_id: int = 0


@dataclass(frozen=True)
class MetadataUpdated(Event):
    media_type: str = ""
    media_id: int = 0
    provider: str = ""
    artwork_downloaded: int = 0


@dataclass(frozen=True)
class MetadataBatchFinished(Event):
    processed: int = 0
    failed: int = 0
    message: str = ""


@dataclass(frozen=True)
class ArtworkUpdated(Event):
    owner_type: str = ""
    owner_id: int = 0
    kind: str = ""


@dataclass(frozen=True)
class PlaybackStarted(Event):
    media_type: str = ""
    media_id: int = 0
    media_file_id: int | None = None
    path: str = ""
    resumed: bool = False


@dataclass(frozen=True)
class PlaybackProgress(Event):
    media_type: str = ""
    media_id: int = 0
    position_seconds: float = 0.0
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class PlaybackStopped(Event):
    media_type: str = ""
    media_id: int = 0
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    completed: bool = False


@dataclass(frozen=True)
class PlaybackFinished(Event):
    media_type: str = ""
    media_id: int = 0


@dataclass(frozen=True)
class ThemeChanged(Event):
    theme: str = "dark"


@dataclass(frozen=True)
class SettingsChanged(Event):
    key: str = ""
    value: Any = None


@dataclass(frozen=True)
class ProviderHealthChanged(Event):
    provider: str = ""
    healthy: bool = False
    message: str = ""


@dataclass(frozen=True)
class DownloadUpdated(Event):
    download_id: int = 0
    state: str = ""
    received: int = 0
    total: int = 0


@dataclass(frozen=True)
class ToastRequested(Event):
    message: str = ""
    level: str = "info"  # info | success | warning | error


class EventBus:
    """Minimal thread-safe synchronous pub/sub bus."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[type, list[Callable[[Any], None]]] = {}

    def subscribe(
        self, event_type: type, handler: Callable[[Any], None]
    ) -> Callable[[], None]:
        """Subscribe; returns an unsubscribe callable."""
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)
        def _unsubscribe() -> None:
            with self._lock:
                try:
                    self._subscribers.get(event_type, []).remove(handler)
                except ValueError:
                    pass
        return _unsubscribe

    def publish(self, event: Any) -> None:
        event_type = type(event)
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))
            handlers += self._subscribers.get(object, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "event handler %r failed for %s", handler, event_type.__name__
                )

    def publish_async(self, event: Any) -> None:
        """Publish from any thread without blocking the caller.

        Handlers run on a daemon thread.
        """
        threading.Thread(
            target=self.publish, args=(event,), daemon=True, name="jmdb-event"
        ).start()
