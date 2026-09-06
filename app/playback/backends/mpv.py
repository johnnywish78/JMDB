"""MPV playback backend (libmpv via python-mpv)."""
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


class MpvBackend(PlaybackBackend):
    id = "mpv"
    name = "MPV"
    capabilities = Capabilities(
        embed=True, pause=True, seek=True, volume=True, mute=True, speed=True,
        audio_tracks=True, subtitle_tracks=True, subtitle_delay=True,
        audio_delay=True, aspect_ratio=True, position_feedback=True,
        fullscreen_hint=True,
    )

    @staticmethod
    def probe() -> tuple[bool, str]:
        try:
            import mpv  # noqa: F401
        except Exception:
            return False, "python-mpv not installed or libmpv missing"
        return True, ""

    def __init__(self, callbacks: BackendCallbacks | None = None) -> None:
        super().__init__(callbacks)
        import mpv

        self._mpv_module = mpv
        self._widget = None
        self._state = "idle"
        self._duration = 0.0
        self._player = mpv.MPV(
            wid=self._window_id(),
            vo="auto",
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,
        )
        self._install_observers()

    def _window_id(self):
        """Create the embed target widget first so MPV can attach to it."""
        from PyQt6.QtWidgets import QWidget

        self._widget = QWidget()
        self._widget.setAttribute(54, True)  # WA_NativeWindow
        return int(self._widget.winId())

    # -- observers ------------------------------------------------------------
    def _install_observers(self) -> None:
        player = self._player

        @player.property_observer("pause")
        def _on_pause(_name, paused):  # pragma: no cover - callback thread
            if not paused and self._state not in ("finished", "stopped"):
                self._set_state("playing")

        @player.property_observer("duration")
        def _on_duration(_name, duration):  # pragma: no cover
            if duration:
                self._duration = float(duration)
                self.callbacks.on_duration(self._duration)

        @player.event_callback("end-file")
        def _on_end(event):  # pragma: no cover
            reason = (event.as_dict() or {}).get("reason", "")
            if reason == "eof":
                self._state = "finished"
                self.callbacks.on_finished()
            else:
                self._state = "stopped"
                self.callbacks.on_state("stopped")

    def _set_state(self, state: str) -> None:
        self._state = state
        self.callbacks.on_state(state)

    # -- lifecycle ----------------------------------------------------------------
    def load(self, path: str, start_position: float = 0.0) -> None:
        options = {}
        if start_position > 0:
            options["start"] = f"+{start_position:.2f}"
        self._state = "loading"
        self.callbacks.on_state("loading")
        self._player.play(path, **options)
        self._set_state("playing")

    def play(self) -> None:
        self._player.pause = False
        self._set_state("playing")

    def pause(self) -> None:
        self._player.pause = True
        self._set_state("paused")

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
        try:
            return float(self._player.playback_time or 0)
        except Exception:
            return 0.0

    @property
    def duration(self) -> float:
        try:
            return float(self._player.duration or self._duration)
        except Exception:
            return self._duration

    # -- controls ------------------------------------------------------------------------
    def seek(self, position_seconds: float) -> None:
        self._player.seek(position_seconds, reference="absolute")

    def set_volume(self, percent: float) -> None:
        self._player.volume = float(percent)

    def set_muted(self, muted: bool) -> None:
        self._player.mute = bool(muted)

    def set_speed(self, rate: float) -> None:
        self._player.speed = float(rate)

    def set_audio_track(self, track: TrackSelection | None) -> None:
        self._player.aid = track.index if track else "no"

    def set_subtitle_track(self, track: TrackSelection | None) -> None:
        self._player.sid = track.index if track else "no"

    def set_subtitle_delay(self, seconds: float) -> None:
        self._player.sub_delay = float(seconds)

    def set_audio_delay(self, seconds: float) -> None:
        self._player.audio_delay = float(seconds)

    def set_aspect_ratio(self, ratio: str) -> None:
        self._player.video_aspect_override = ratio if ratio != "auto" else -1

    # -- tracks ---------------------------------------------------------------------------
    def audio_tracks(self) -> list[TrackSelection]:
        return self._tracks_of("audio")

    def subtitle_tracks(self) -> list[TrackSelection]:
        return self._tracks_of("sub")

    def _tracks_of(self, prefix: str) -> list[TrackSelection]:
        tracks = []
        try:
            raw = self._player.__getattr__(f"{prefix}_tracks") or []
            for track in raw:
                index = track.get("id")
                if index is None:
                    continue
                title = track.get("title") or track.get("lang") or f"Track {index}"
                tracks.append(
                    TrackSelection(
                        index=index,
                        kind="audio" if prefix == "audio" else "subtitle",
                        language=track.get("lang", "") or "",
                        title=title,
                    )
                )
        except Exception as exc:
            logger.debug("track listing failed: %s", exc)
        return tracks

    # -- embedding ---------------------------------------------------------------------------
    def video_widget(self):
        return self._widget

    def teardown(self) -> None:
        try:
            self._player.terminate()
        except Exception:
            pass
