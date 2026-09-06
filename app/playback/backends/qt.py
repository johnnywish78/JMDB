"""Qt Multimedia playback backend.

Qt's media stack on Linux depends on the system's FFmpeg/GStreamer setup;
this backend is used when VLC and MPV are unavailable. It is fully guarded:
import failures or a missing media backend degrade to 'unavailable'.
"""
from __future__ import annotations

import logging

from app.domain.value_objects import TrackSelection
from app.playback.backends.base import (
    BackendCallbacks,
    Capabilities,
    PlaybackBackend,
    PlaybackError,
)

logger = logging.getLogger(__name__)


class QtBackend(PlaybackBackend):
    id = "qt"
    name = "Qt Multimedia"
    capabilities = Capabilities(
        embed=True, pause=True, seek=True, volume=True, mute=True, speed=True,
        position_feedback=True,
    )

    @staticmethod
    def probe() -> tuple[bool, str]:
        try:
            from PyQt6.QtMultimedia import QMediaPlayer  # noqa: F401
        except Exception:
            return False, "PyQt6-Multimedia not installed"
        return True, ""

    def __init__(self, callbacks: BackendCallbacks | None = None) -> None:
        super().__init__(callbacks)
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink

        self._QUrl = QUrl
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._video_sink = QVideoSink()
        self._player.setVideoSink(self._video_sink)
        self._widget = None
        self._player_duration = 0.0

        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.errorOccurred.connect(self._on_error)
        self._player.durationChanged.connect(self._on_duration)
        self._player.positionChanged.connect(lambda ms: self.callbacks.on_position(ms / 1000.0))

    # -- Qt slots ---------------------------------------------------------------
    def _on_state(self, state) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer

        mapping = {
            QMediaPlayer.PlaybackState.PlayingState: "playing",
            QMediaPlayer.PlaybackState.PausedState: "paused",
            QMediaPlayer.PlaybackState.StoppedState: "stopped",
        }
        self.callbacks.on_state(mapping.get(state, "stopped"))

    def _on_media_status(self, status) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.callbacks.on_finished()

    def _on_duration(self, ms: int) -> None:
        self._player_duration = ms / 1000.0
        self.callbacks.on_duration(self._player_duration)

    def _on_error(self, *args) -> None:
        # QMediaPlayer.errorOccurred has two overloads —
        # (error, errorString) and (source, error, errorString) — and PyQt6
        # picks either depending on version. Handle both.
        if len(args) >= 3:
            _source, error, error_string = args[-3:]
        elif len(args) == 2:
            error, error_string = args
        else:
            error, error_string = args[0] if args else "unknown", ""
        self.callbacks.on_error(str(error_string or error))

    # -- lifecycle ------------------------------------------------------------------
    def load(self, path: str, start_position: float = 0.0) -> None:
        from PyQt6.QtCore import QUrl as Url

        self._player.setSource(Url.fromUserInput(path))
        if start_position > 0:
            self._player.setPosition(int(start_position * 1000))
        self.play()

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()
        self.callbacks.on_state("stopped")

    # -- state -------------------------------------------------------------------------
    @property
    def state(self) -> str:
        from PyQt6.QtMultimedia import QMediaPlayer

        mapping = {
            QMediaPlayer.PlaybackState.PlayingState: "playing",
            QMediaPlayer.PlaybackState.PausedState: "paused",
        }
        return mapping.get(self._player.playbackState(), "stopped")

    @property
    def position(self) -> float:
        return self._player.position() / 1000.0

    @property
    def duration(self) -> float:
        return self._player.duration() / 1000.0 or self._player_duration

    # -- controls ------------------------------------------------------------------------
    def seek(self, position_seconds: float) -> None:
        self._player.setPosition(int(position_seconds * 1000))

    def set_volume(self, percent: float) -> None:
        from PyQt6.QtCore import QAudio

        self._audio_output.setVolume(int(percent) / 100.0)

    def set_muted(self, muted: bool) -> None:
        self._audio_output.setMuted(muted)

    def set_speed(self, rate: float) -> None:
        self._player.setPlaybackRate(rate)

    # -- embedding ---------------------------------------------------------------------------
    def video_widget(self):
        if self._widget is None:
            from PyQt6.QtMultimediaWidgets import QVideoWidget

            self._video_sink = None
            widget = QVideoWidget()
            self._player.setVideoOutput(widget)
            self._widget = widget
        return self._widget

    def teardown(self) -> None:
        try:
            self._player.stop()
            self._player.deleteLater()
            self._audio_output.deleteLater()
        except Exception:
            pass
