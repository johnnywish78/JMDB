"""Qt Multimedia backend — zero native deps beyond PyQt6, codec-limited."""
from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget

from app.playback.backends.base import AbstractPlaybackBackend, BackendDescriptor

try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    _QT_MM_OK = True
    _QT_MM_ERR = ""
except ImportError as exc:  # pragma: no cover - env-dependent
    _QT_MM_OK = False
    _QT_MM_ERR = str(exc)


class QtMultimediaBackend(AbstractPlaybackBackend):
    backend_id = "qt"
    backend_name = "Qt Multimedia"

    def __init__(self, parent=None):
        if not _QT_MM_OK:
            raise RuntimeError(f"Qt Multimedia unavailable: {_QT_MM_ERR}")
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._video = QVideoWidget()
        self._player.setVideoOutput(self._video)
        self._position = 0
        self._duration = 0
        self._player.positionChanged.connect(lambda ms: self._pos(ms))
        self._player.durationChanged.connect(lambda ms: self._dur(ms))
        self._player.mediaStatusChanged.connect(self._status)
        self._player.playbackStateChanged.connect(
            lambda st: self.playingChanged.emit(st == QMediaPlayer.PlaybackState.PlayingState))
        self._player.errorOccurred.connect(
            lambda err, desc="": self.errorOccurred.emit(desc or str(err)))

    @classmethod
    def descriptor(cls) -> BackendDescriptor:
        return BackendDescriptor(cls.backend_id, cls.backend_name, _QT_MM_OK, _QT_MM_ERR)

    def video_widget(self) -> QWidget:
        return self._video

    def open_media(self, path: str, start_seconds: int = 0) -> None:
        self._player.setSource(QUrl.fromLocalFile(path))
        # QMediaPlayer has no pre-play seek; play then seek on first position signal
        self._pending_seek = start_seconds

    def _pos(self, ms: int) -> None:
        self._position = ms // 1000
        self.positionChanged.emit(self._position)

    def _dur(self, ms: int) -> None:
        self._duration = ms // 1000
        self.durationChanged.emit(self._duration)

    def _status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia and getattr(self, "_pending_seek", None):
            self._player.setPosition(int(self._pending_seek) * 1000)
            self._pending_seek = None
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()

    def play(self) -> None:        self._player.play()
    def pause(self) -> None:       self._player.pause()
    def stop(self) -> None:        self._player.stop()
    def seek_s(self, s: int) -> None: self._player.setPosition(max(0, int(s)) * 1000)
    def set_speed(self, speed: float) -> None: self._player.setPlaybackRate(float(speed))
    def set_volume(self, percent: int) -> None:  self._audio.setVolume(max(0, min(100, percent)) / 100)
    def is_playing(self) -> bool:  return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    def position_s(self) -> int:   return self._position
    def duration_s(self) -> int:   return self._duration
