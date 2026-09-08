"""Playback backend contract. All backends are QObjects owning a video widget."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget


@dataclass
class BackendDescriptor:
    id: str           # 'mpv' | 'vlc' | 'qt' | 'external'
    name: str
    available: bool
    reason: str = ""  # populated when not available


class AbstractPlaybackBackend(QObject):
    positionChanged = pyqtSignal(int)        # seconds
    durationChanged = pyqtSignal(int)        # seconds
    playingChanged = pyqtSignal(bool)
    finished = pyqtSignal()
    errorOccurred = pyqtSignal(str)

    backend_id = "abstract"
    backend_name = "Abstract"

    def video_widget(self) -> QWidget:        # pragma: no cover - interface
        raise NotImplementedError

    def open_media(self, path: str, start_seconds: int = 0) -> None:
        raise NotImplementedError

    def play(self) -> None:                   raise NotImplementedError
    def pause(self) -> None:                  raise NotImplementedError
    def stop(self) -> None:                   raise NotImplementedError
    def seek_s(self, seconds: int) -> None:   raise NotImplementedError
    def set_speed(self, speed: float) -> None: raise NotImplementedError
    def set_volume(self, percent: int) -> None: raise NotImplementedError
    def is_playing(self) -> bool:             raise NotImplementedError
    def position_s(self) -> int:              raise NotImplementedError
    def duration_s(self) -> int:              raise NotImplementedError
