"""UI context: the object handed to every screen.

Contains services, the Qt event bridge, async helpers, the image loader,
toast manager, and the router. Screens never touch repositories or SQL.
"""
from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QPixmap

from app.services_app.coordinator import AppServices

logger = logging.getLogger(__name__)

ASSETS = Path(__file__).resolve().parent.parent / ".." / "assets"


def icon(name: str) -> QIcon:
    """Load a themed icon by name (colorized at render time via QSS)."""
    path = ASSETS / "icons" / f"{name}.svg"
    if path.exists():
        return QIcon(str(path))
    return QIcon()


def asset_path(relative: str) -> Path:
    return ASSETS / relative


class EventBridge(QObject):
    """Marshals bus events (any thread) into Qt signals (main thread)."""

    received = pyqtSignal(object)

    def __init__(self, bus) -> None:
        super().__init__()
        self._bus = bus
        self._unsubscribe = bus.subscribe(object, self._on_event)

    def _on_event(self, event) -> None:
        # Qt auto-connections are queued when emitted from a worker thread
        self.received.emit(event)

    def shutdown(self) -> None:
        self._unsubscribe()


class _WorkerSignals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable, args: tuple) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = _WorkerSignals()

    def run(self) -> None:  # pragma: no cover - thread body
        try:
            self.signals.done.emit(self.fn(*self.args))
        except Exception:
            logger.exception("async task failed")
            self.signals.failed.emit(traceback.format_exc(limit=3))


def run_async(fn: Callable, on_done: Callable | None = None, on_error: Callable | None = None) -> None:
    """Run fn in the thread pool; callbacks run on the Qt main thread."""
    task = _Task(fn, ())
    if on_done is not None:
        task.signals.done.connect(on_done, Qt.ConnectionType.QueuedConnection)
    if on_error is not None:
        task.signals.failed.connect(on_error, Qt.ConnectionType.QueuedConnection)
    QThreadPool.globalInstance().start(task)


class ImageLoader(QObject):
    """Async, cached image loading for posters/stills/avatars.

    Loads local files (and resizes) off the UI thread. Results are cached
    in an LRU keyed by (path, width).
    """
    ready = pyqtSignal(str, QPixmap)

    def __init__(self, max_cache: int = 400) -> None:
        super().__init__()
        self._cache: dict[str, QPixmap] = {}
        self._order: list[str] = []
        self._max = max_cache
        self._loading: set[str] = set()

    def request(self, key: str, path: str, width: int) -> None:
        if not path:
            return
        cache_key = f"{path}|{width}"
        if cache_key in self._cache:
            self.ready.emit(key, self._cache[cache_key])
            return
        if cache_key in self._loading:
            return
        self._loading.add(cache_key)

        def load(path=path, width=width, cache_key=cache_key, key=key):
            pixmap = _load_pixmap(path, width)
            return key, cache_key, pixmap

        def done(result):
            key, cache_key, pixmap = result
            self._loading.discard(cache_key)
            if pixmap is not None:
                self._store(cache_key, pixmap)
                self.ready.emit(key, pixmap)

        run_async(load, done)

    def _store(self, cache_key: str, pixmap: QPixmap) -> None:
        self._cache[cache_key] = pixmap
        self._order.append(cache_key)
        while len(self._order) > self._max:
            oldest = self._order.pop(0)
            self._cache.pop(oldest, None)


def _load_pixmap(path: str, width: int) -> QPixmap | None:
    try:
        if path.lower().endswith(".svg"):
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtCore import QByteArray
            from PyQt6.QtGui import QPainter

            data = Path(path).read_bytes()
            renderer = QSvgRenderer(QByteArray(data))
            ratio = renderer.defaultSize().height() / max(1, renderer.defaultSize().width())
            image = QImage(int(width), max(1, int(width * ratio)), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            return QPixmap.fromImage(image)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None
        if width and pixmap.width() > width:
            return pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        return pixmap
    except Exception:
        logger.debug("image load failed: %s", path, exc_info=True)
        return None


class UIContext:
    """Everything a screen needs."""

    def __init__(self, services: AppServices, bridge: EventBridge, router, theme_manager, player_factory) -> None:
        self.services = services
        self.bridge = bridge
        self.router = router
        self.themes = theme_manager
        self.images = ImageLoader()
        self._player_factory = player_factory
        self._event_handlers: list[tuple[type, Callable]] = []
        self.bridge.received.connect(self._dispatch)
        self.playback_controller = None  # set by main window

    # -- events -------------------------------------------------------------
    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._event_handlers.append((event_type, handler))

    def _dispatch(self, event) -> None:
        for event_type, handler in list(self._event_handlers):
            if isinstance(event, event_type):
                try:
                    handler(event)
                except Exception:
                    logger.exception("UI event handler failed for %s", type(event).__name__)

    # -- convenience ------------------------------------------------------------
    @property
    def svc(self) -> AppServices:
        return self.services

    @property
    def profile_id(self) -> int:
        return self.services.profile.id

    def toast(self, message: str, level: str = "info") -> None:
        from app.domain.events import ToastRequested

        self.services.events.publish(ToastRequested(message=message, level=level))

    def open_player(self, playable, queue=None) -> None:
        if self._player_factory is not None:
            self._player_factory(playable, queue)
