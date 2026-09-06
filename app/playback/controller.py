"""Playback controller: bridges the player window UI ↔ backend ↔ database.

Runs on the Qt main thread. Polls the backend for position (backends that
support it), saves resume positions periodically, finishes sessions on
EOF/stop, and advances the queue.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.config.settings import SettingsService
from app.domain.value_objects import PlayableItem
from app.playback.backends.base import BackendCallbacks, PlaybackBackend, PlaybackError
from app.playback.service import PlaybackService

logger = logging.getLogger(__name__)

SAVE_INTERVAL = 5.0  # seconds between resume saves
POLL_INTERVAL = 250  # ms


class PlaybackController(QObject):
    position_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(float)
    state_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal(object)  # PlayableItem
    session_started = pyqtSignal(object)  # PlayableItem
    queue_advanced = pyqtSignal(object)  # PlayableItem

    def __init__(self, service: PlaybackService, settings: SettingsService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.settings = settings
        self.backend: PlaybackBackend | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(int(SAVE_INTERVAL * 1000))
        self._save_timer.timeout.connect(self._save_progress)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL)
        self._poll_timer.timeout.connect(self._poll)
        self._queue: list[PlayableItem] = []
        self._external_mode = False

    # -- playback ---------------------------------------------------------------
    def play_item(
        self,
        item: PlayableItem,
        profile_id: int,
        queue: list[PlayableItem] | None = None,
    ) -> None:
        self.stop(clear_queue=False)
        self._queue = queue or [item]
        self._start(item, profile_id)

    def _start(self, item: PlayableItem, profile_id: int) -> None:
        try:
            backend_id, _name = self.service.resolve_backend()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return

        if backend_id == "external":
            self._external_mode = True
            try:
                self.service.play_external(item, profile_id)
                self.session_started.emit(item)
            except Exception as exc:
                self.error_occurred.emit(str(exc))
            return

        self._external_mode = False
        backend_cls = self.service.resolve_backend and self._backend_class(backend_id)
        if backend_cls is None:
            self.error_occurred.emit(f"backend {backend_id} could not be loaded")
            return
        try:
            backend = backend_cls(callbacks=self._callbacks())
        except Exception as exc:
            logger.exception("failed to init %s backend", backend_id)
            self.error_occurred.emit(f"Failed to initialize {backend_id}: {exc}")
            return
        self.backend = backend
        self.service.attach_backend(backend)
        session = self.service.start_session(item, profile_id, backend_id, queue=self._queue)
        try:
            backend.load(item.path, session.start_position)
        except Exception as exc:
            self.error_occurred.emit(f"Failed to open {item.path}: {exc}")
            return
        self.session_started.emit(item)
        self.state_changed.emit(backend.state)
        self._poll_timer.start()
        self._save_timer.start()

    def _backend_class(self, backend_id: str):
        from app.playback.service import _load_backends

        return _load_backends().get(backend_id)

    def _callbacks(self) -> BackendCallbacks:
        return BackendCallbacks(
            on_state=lambda s: self.state_changed.emit(s),
            on_position=lambda p: self.position_changed.emit(p),
            on_duration=lambda d: self.duration_changed.emit(d),
            on_error=lambda e: self.error_occurred.emit(e),
            on_finished=self._on_finished,
        )

    # -- controls ----------------------------------------------------------------
    def _with_backend(self, method: str, *args) -> None:
        if self.backend is None:
            return
        try:
            getattr(self.backend, method)(*args)
        except PlaybackError as exc:
            self.error_occurred.emit(str(exc))
        except Exception as exc:
            logger.exception("backend call %s failed", method)
            self.error_occurred.emit(str(exc))

    def toggle_pause(self) -> None:
        if self.backend is None:
            return
        if self.backend.state == "playing":
            self._with_backend("pause")
        else:
            self._with_backend("play")

    def pause(self) -> None:
        self._with_backend("pause")

    def resume(self) -> None:
        self._with_backend("play")

    def stop(self, clear_queue: bool = True) -> None:
        if clear_queue:
            self._queue = []
        self._poll_timer.stop()
        self._save_timer.stop()
        position = duration = 0.0
        if self.backend is not None:
            try:
                position = self.backend.position
                duration = self.backend.duration
                self.backend.stop()
            except Exception:
                pass
        self._finish_session(position, duration, completed=False)
        if self.backend is not None:
            try:
                self.backend.teardown()
            except Exception:
                pass
            self.backend = None

    def seek(self, seconds: float) -> None:
        self._with_backend("seek", max(0.0, seconds))

    def seek_relative(self, delta: float) -> None:
        if self.backend is not None:
            self.seek(self.backend.position + delta)

    def set_volume(self, percent: float) -> None:
        self._with_backend("set_volume", percent)

    def set_muted(self, muted: bool) -> None:
        self._with_backend("set_muted", muted)

    def set_speed(self, rate: float) -> None:
        self._with_backend("set_speed", rate)

    def set_audio_track(self, track) -> None:
        self._with_backend("set_audio_track", track)

    def set_subtitle_track(self, track) -> None:
        self._with_backend("set_subtitle_track", track)

    def set_subtitle_delay(self, seconds: float) -> None:
        self._with_backend("set_subtitle_delay", seconds)

    def set_audio_delay(self, seconds: float) -> None:
        self._with_backend("set_audio_delay", seconds)

    # -- queue ---------------------------------------------------------------------
    def next(self) -> None:
        if not self._queue:
            return
        current = self.service.session.current if self.service.session else None
        for i, queued in enumerate(self._queue):
            if current and queued.path == current.path:
                if i + 1 < len(self._queue):
                    self.stop(clear_queue=False)
                    self._start(self._queue[i + 1], self._profile_id())
                    self.queue_advanced.emit(self._queue[i + 1])
                    return
                break
        self.stop()

    def previous(self) -> None:
        if not self._queue:
            return
        current = self.service.session.current if self.service.session else None
        for i, queued in enumerate(self._queue):
            if current and queued.path == current.path:
                if i > 0:
                    self.stop(clear_queue=False)
                    self._start(self._queue[i - 1], self._profile_id())
                    self.queue_advanced.emit(self._queue[i - 1])
                    return
                break
        self.stop()

    def _profile_id(self) -> int:
        session = self.service.session
        return session.profile_id if session else 1

    # -- internal ---------------------------------------------------------------------
    def _poll(self) -> None:
        if self.backend is None:
            return
        try:
            self.position_changed.emit(self.backend.position)
            if self.backend.duration:
                self.duration_changed.emit(self.backend.duration)
        except Exception:
            pass

    def _save_progress(self) -> None:
        if self.backend is None:
            return
        try:
            self.service.save_progress(self.backend.position, self.backend.duration)
        except Exception:
            logger.exception("failed to save playback progress")

    def _on_finished(self) -> None:
        position = duration = 0.0
        if self.backend is not None:
            try:
                position = self.backend.position
                duration = self.backend.duration
            except Exception:
                pass
        item = self.service.session.current if self.service.session else None
        self._finish_session(position, duration, completed=True)
        if item is not None:
            self.finished.emit(item)
        # advance queue
        if self.service.session is None and self._queue:
            current_path = item.path if item else ""
            for i, queued in enumerate(self._queue):
                if queued.path == current_path and i + 1 < len(self._queue):
                    next_item = self._queue[i + 1]
                    self._poll_timer.stop()
                    self._save_timer.stop()
                    if self.backend is not None:
                        try:
                            self.backend.teardown()
                        except Exception:
                            pass
                        self.backend = None
                    self._start(next_item, self._profile_id())
                    self.queue_advanced.emit(next_item)
                    return

    def _finish_session(self, position: float, duration: float, completed: bool) -> None:
        try:
            self.service.finish_session(position, duration, completed)
        except Exception:
            logger.exception("failed to finish playback session")

    # -- capabilities --------------------------------------------------------------------
    def capabilities(self):
        return self.backend.capabilities if self.backend else None
