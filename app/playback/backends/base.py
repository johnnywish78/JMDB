"""Playback backend abstraction.

A backend plays one file at a time and reports through callbacks. The UI
never imports VLC/MPV/Qt Multimedia directly — it talks to this interface
and enables/disables features based on :class:`Capabilities`.

Callbacks may fire from non-Qt threads; the controller marshals them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.domain.value_objects import TrackSelection


@dataclass
class Capabilities:
    embed: bool = False          # renders video inside JMDB's player window
    pause: bool = False
    seek: bool = False
    volume: bool = False
    mute: bool = False
    speed: bool = False
    audio_tracks: bool = False
    subtitle_tracks: bool = False
    subtitle_delay: bool = False
    audio_delay: bool = False
    aspect_ratio: bool = False
    position_feedback: bool = False  # reports position/duration while playing
    fullscreen_hint: bool = False    # backend handles fullscreen natively


@dataclass
class BackendCallbacks:
    on_state: Callable[[str], None] = field(default=lambda s: None)
    on_position: Callable[[float], None] = field(default=lambda p: None)
    on_duration: Callable[[float], None] = field(default=lambda d: None)
    on_error: Callable[[str], None] = field(default=lambda e: None)
    on_finished: Callable[[], None] = field(default=lambda: None)
    on_tracks_changed: Callable[[], None] = field(default=lambda: None)


class PlaybackError(Exception):
    pass


class PlaybackBackend(ABC):
    """Abstract single-file player."""

    id = "base"
    name = "Base"
    capabilities = Capabilities()

    def __init__(self, callbacks: BackendCallbacks | None = None) -> None:
        self.callbacks = callbacks or BackendCallbacks()

    # -- availability -----------------------------------------------------------
    @staticmethod
    def probe() -> tuple[bool, str]:
        """(available, reason when unavailable). Never raises."""
        return False, "not implemented"

    # -- lifecycle -----------------------------------------------------------------
    @abstractmethod
    def load(self, path: str, start_position: float = 0.0) -> None:
        """Load a media file. Paths with spaces/Unicode must work verbatim."""

    @abstractmethod
    def play(self) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    def set_callbacks(self, callbacks: BackendCallbacks) -> None:
        self.callbacks = callbacks

    # -- state -------------------------------------------------------------------
    @property
    @abstractmethod
    def state(self) -> str:
        """idle | loading | playing | paused | stopped | finished | error"""

    @property
    @abstractmethod
    def position(self) -> float: ...

    @property
    @abstractmethod
    def duration(self) -> float: ...

    # -- optional controls (guarded by capabilities) ----------------------------------
    def seek(self, position_seconds: float) -> None:
        raise PlaybackError(f"{self.name} does not support seeking")

    def set_volume(self, percent: float) -> None:
        raise PlaybackError(f"{self.name} does not support volume")

    def set_muted(self, muted: bool) -> None:
        raise PlaybackError(f"{self.name} does not support mute")

    def set_speed(self, rate: float) -> None:
        raise PlaybackError(f"{self.name} does not support speed")

    def set_audio_track(self, track: TrackSelection | None) -> None:
        raise PlaybackError(f"{self.name} does not support audio track selection")

    def set_subtitle_track(self, track: TrackSelection | None) -> None:
        raise PlaybackError(f"{self.name} does not support subtitle track selection")

    def set_subtitle_delay(self, seconds: float) -> None:
        raise PlaybackError(f"{self.name} does not support subtitle delay")

    def set_audio_delay(self, seconds: float) -> None:
        raise PlaybackError(f"{self.name} does not support audio delay")

    def set_aspect_ratio(self, ratio: str) -> None:
        raise PlaybackError(f"{self.name} does not support aspect ratio")

    # -- tracks ----------------------------------------------------------------------
    def audio_tracks(self) -> list[TrackSelection]:
        return []

    def subtitle_tracks(self) -> list[TrackSelection]:
        return []

    # -- embedding -----------------------------------------------------------------------
    def video_widget(self):
        """QWidget rendering the video, or None when not embeddable."""
        return None

    def teardown(self) -> None:
        """Release backend resources."""
