"""VLC playback backend (python-vlc + system VLC)."""
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


class VlcBackend(PlaybackBackend):
    id = "vlc"
    name = "VLC"
    capabilities = Capabilities(
        embed=True, pause=True, seek=True, volume=True, mute=True, speed=True,
        audio_tracks=True, subtitle_tracks=True, subtitle_delay=True,
        audio_delay=True, aspect_ratio=True, position_feedback=True,
        fullscreen_hint=True,
    )

    @staticmethod
    def probe() -> tuple[bool, str]:
        try:
            import vlc  # noqa: F401
        except Exception:
            return False, "python-vlc not installed"
        try:
            import ctypes.util

            if not (ctypes.util.find_library("vlc") or ctypes.util.find_library("libvlc")):
                import shutil

                if not shutil.which("vlc"):
                    return False, "VLC not installed (libvlc not found)"
            return True, ""
        except Exception as exc:
            return False, f"libvlc probe failed: {exc}"

    def __init__(self, callbacks: BackendCallbacks | None = None) -> None:
        super().__init__(callbacks)
        import vlc

        self._vlc = vlc
        self._instance = vlc.Instance("--no-video-title-show", "--quiet")
        if self._instance is None:
            raise PlaybackError("could not create VLC instance")
        self._player = self._instance.media_player_new()
        self._media = None
        self._state = "idle"
        self._duration = 0.0
        self._widget = None
        self._tracks: dict[str, list[TrackSelection]] = {"audio": [], "subtitle": []}
        self._install_event_handlers()

    # -- events ---------------------------------------------------------------
    def _install_event_handlers(self) -> None:
        player_events = self._player.event_manager()
        player_events.event_attach(
            self._vlc.EventType.MediaPlayerPlaying, lambda *_: self._set_state("playing")
        )
        player_events.event_attach(
            self._vlc.EventType.MediaPlayerPaused, lambda *_: self._set_state("paused")
        )
        player_events.event_attach(
            self._vlc.EventType.MediaPlayerEndReached, lambda *_: self._on_end()
        )
        player_events.event_attach(
            self._vlc.EventType.MediaPlayerEncounteredError,
            lambda *_: self._on_error(),
        )
        player_events.event_attach(
            self._vlc.EventType.MediaPlayerTimeChanged,
            lambda event: self.callbacks.on_position(event.u.new_time / 1000.0),
        )
        player_events.event_attach(
            self._vlc.EventType.MediaPlayerLengthChanged,
            lambda event: self._set_duration(event.u.new_length / 1000.0),
        )

    def _set_state(self, state: str) -> None:
        self._state = state
        self.callbacks.on_state(state)

    def _set_duration(self, duration: float) -> None:
        self._duration = duration
        self.callbacks.on_duration(duration)

    def _on_end(self) -> None:
        self._state = "finished"
        self.callbacks.on_finished()

    def _on_error(self) -> None:
        self._state = "error"
        self.callbacks.on_error("VLC reported a playback error")

    # -- lifecycle ------------------------------------------------------------------
    def load(self, path: str, start_position: float = 0.0) -> None:
        self._media = self._instance.media_new(path)
        if self._media is None:
            raise PlaybackError(f"VLC could not open {path}")
        self._player.set_media(self._media)
        self._state = "loading"
        self._parse_tracks()
        self.callbacks.on_state("loading")
        self.play()
        if start_position > 0:
            self.seek(start_position)

    def _parse_tracks(self) -> None:
        self._media.parse_async() if hasattr(self._media, "parse_async") else self._media.parse()

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()
        self._state = "stopped"
        self.callbacks.on_state("stopped")

    # -- state ------------------------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def position(self) -> float:
        return self._player.get_time() / 1000.0

    @property
    def duration(self) -> float:
        if self._duration <= 0:
            duration = self._player.get_length()
            if duration > 0:
                self._duration = duration / 1000.0
        return self._duration

    # -- controls ------------------------------------------------------------------------
    def seek(self, position_seconds: float) -> None:
        self._player.set_time(int(position_seconds * 1000))

    def set_volume(self, percent: float) -> None:
        self._player.audio_set_volume(int(percent))

    def set_muted(self, muted: bool) -> None:
        self._player.audio_set_mute(1 if muted else 0)

    def set_speed(self, rate: float) -> None:
        self._player.set_rate(rate)

    def set_audio_track(self, track: TrackSelection | None) -> None:
        if track is None:
            self._player.audio_set_track(-1)
        else:
            self._player.audio_set_track(track.index)

    def set_subtitle_track(self, track: TrackSelection | None) -> None:
        if track is None:
            self._player.video_set_spu(-1)  # disable subtitles
        else:
            self._player.video_set_spu(track.index)

    def set_subtitle_delay(self, seconds: float) -> None:
        self._player.set_subtitle_delay(int(seconds * 1000000))

    def set_audio_delay(self, seconds: float) -> None:
        self._player.set_audio_delay(int(seconds * 1000000))

    def set_aspect_ratio(self, ratio: str) -> None:
        self._player.video_set_aspect_ratio(ratio if ratio != "auto" else None)

    # -- tracks ---------------------------------------------------------------------------
    def audio_tracks(self) -> list[TrackSelection]:
        self._refresh_tracks()
        return self._tracks["audio"]

    def subtitle_tracks(self) -> list[TrackSelection]:
        self._refresh_tracks()
        return self._tracks["subtitle"]

    def _refresh_tracks(self) -> None:
        try:
            audio = []
            description = self._player.audio_get_track_description() or []
            for index, name in description:
                audio.append(TrackSelection(index=index, kind="audio", title=str(name)))
            self._tracks["audio"] = audio
            subs = []
            for index, name in (self._player.video_get_spu_description() or []):
                subs.append(TrackSelection(index=index, kind="subtitle", title=str(name)))
            self._tracks["subtitle"] = subs
        except Exception as exc:
            logger.debug("track listing failed: %s", exc)

    # -- embedding ---------------------------------------------------------------------------
    def video_widget(self):
        if self._widget is None:
            from PyQt6.QtWidgets import QWidget

            self._widget = QWidget()
            self._widget.setAttribute(54, True)  # WA_NativeWindow: needed for XEmbed
            win_id = int(self._widget.winId())
            if sys_platform := _platform():
                setter = {
                    "linux": self._player.set_xwindow,
                    "windows": self._player.set_hwnd,
                    "macos": self._player.set_nsobject,
                }.get(sys_platform)
                if setter:
                    setter(win_id)
        return self._widget

    def teardown(self) -> None:
        try:
            self._player.stop()
            self._player.release()
            self._instance.release()
        except Exception:
            pass


def _platform() -> str:
    import sys

    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("darwin"):
        return "macos"
    return ""
