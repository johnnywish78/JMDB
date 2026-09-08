"""Native backends: python-vlc + python-mpv embeds, and the 'external' handoff.
Every class is import-guarded: probing availability never throws."""
from __future__ import annotations

import shutil
import subprocess
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

from app.playback.backends.base import AbstractPlaybackBackend, BackendDescriptor


def _spec_ok(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


# ────────────────────────────────────────────────────────── VLC
class VLCBackend(AbstractPlaybackBackend):
    backend_id = "vlc"
    backend_name = "VLC (libvlc)"

    def __init__(self, parent=None):
        import vlc  # local import: probing elsewhere never needs libvlc

        super().__init__(parent)
        self._vlc_mod = vlc
        self._instance = vlc.Instance("--no-video-title-show")
        self._player = self._instance.media_player_new()
        self._frame = QFrame()
        self._frame.setStyleSheet("background:#000")
        self._duration = 0
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll)
        self._ended_emitted = False

    @classmethod
    def descriptor(cls) -> BackendDescriptor:
        if not _spec_ok("vlc"):
            return BackendDescriptor(cls.backend_id, cls.backend_name, False,
                                     "python-vlc package not installed")
        try:
            import vlc

            vlc.Instance()
            return BackendDescriptor(cls.backend_id, cls.backend_name, True)
        except Exception as exc:
            return BackendDescriptor(cls.backend_id, cls.backend_name, False,
                                     f"libvlc not loadable: {exc}")

    def video_widget(self) -> QWidget:
        return self._frame

    def _embed(self) -> None:
        wid = int(self._frame.winId())
        if sys.platform.startswith("linux"):
            self._player.set_xwindow(wid)
        elif sys.platform == "win32":
            self._player.set_hwnd(wid)
        elif sys.platform == "darwin":
            self._player.set_nsobject(wid)

    def open_media(self, path: str, start_seconds: int = 0) -> None:
        self._embed()
        media = self._instance.media_new(path)
        if start_seconds > 0:
            media.add_option(f"start-time={start_seconds}")
        self._player.set_media(media)
        self._ended_emitted = False

    def _poll(self) -> None:
        pos = int(self._player.get_time() / 1000)
        self.positionChanged.emit(max(0, pos))
        dur = int(self._player.get_length() / 1000)
        if dur > 0 and dur != self._duration:
            self._duration = dur
            self.durationChanged.emit(dur)
        state = self._player.get_state()
        ended_states = {self._vlc_mod.State.Ended, self._vlc_mod.State.Error}
        if state in ended_states and not self._ended_emitted:
            self._ended_emitted = True
            self.finished.emit()

    def play(self) -> None:
        self._player.play()
        self._timer.start()
        self.playingChanged.emit(True)

    def pause(self) -> None:
        self._player.pause()
        self.playingChanged.emit(False)

    def stop(self) -> None:
        self._timer.stop()
        self._player.stop()

    def seek_s(self, s: int) -> None:    self._player.set_time(int(s) * 1000)
    def set_speed(self, speed: float) -> None: self._player.set_rate(float(speed))
    def set_volume(self, percent: int) -> None: self._player.audio_set_volume(int(percent))
    def is_playing(self) -> bool:        return self._player.is_playing() == 1
    def position_s(self) -> int:         return max(0, int(self._player.get_time() / 1000))
    def duration_s(self) -> int:         return max(self._duration, 0)


# ────────────────────────────────────────────────────────── MPV
class MPVBackend(AbstractPlaybackBackend):
    backend_id = "mpv"
    backend_name = "MPV (libmpv)"

    def __init__(self, parent=None):
        import mpv

        super().__init__(parent)
        self._frame = QFrame()
        self._frame.setStyleSheet("background:#000")
        self._mpv = mpv.MPV(wid=str(int(self._frame.winId())), keep_open=True, ytdl=False,
                            log_handler=lambda *a: None)
        self._position = 0
        self._duration = 0
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._poll)
        self._mpv.observe_property("duration", self._on_duration)
        self._mpv.observe_property("eof-reached", self._on_eof)

    @classmethod
    def descriptor(cls) -> BackendDescriptor:
        if not _spec_ok("mpv"):
            return BackendDescriptor(cls.backend_id, cls.backend_name, False,
                                     "python-mpv package not installed")
        try:
            import mpv

            mpv.MPV()
            return BackendDescriptor(cls.backend_id, cls.backend_name, True)
        except (OSError, AttributeError) as exc:
            return BackendDescriptor(cls.backend_id, cls.backend_name, False,
                                     f"libmpv not loadable: {exc}")

    def video_widget(self) -> QWidget:
        return self._frame

    def _on_duration(self, _name, value):
        if isinstance(value, (int, float)) and value > 0:
            self._duration = int(value)
            self.durationChanged.emit(self._duration)

    def _on_eof(self, _name, value):
        if value:
            self.finished.emit()

    def _poll(self) -> None:
        try:
            pos = self._mpv.time_pos
            if pos is not None:
                self._position = int(pos)
                self.positionChanged.emit(self._position)
        except Exception:
            pass

    def open_media(self, path: str, start_seconds: int = 0) -> None:
        self._mpv.command("loadfile", path, "replace",
                          0, f"start={max(0, start_seconds)}")
        self._mpv.pause = True

    def play(self) -> None:
        self._mpv.pause = False
        self._timer.start()
        self.playingChanged.emit(True)

    def pause(self) -> None:
        self._mpv.pause = True
        self.playingChanged.emit(False)

    def stop(self) -> None:
        self._timer.stop()
        self._mpv.command("stop")

    def seek_s(self, s: int) -> None:    self._mpv.command("seek", int(s), "absolute")
    def set_speed(self, speed: float) -> None: self._mpv.speed = float(speed)
    def set_volume(self, percent: int) -> None: self._mpv.volume = int(percent)
    def is_playing(self) -> bool:        return bool(self._position is not None and not self._mpv.pause)
    def position_s(self) -> int:         return self._position
    def duration_s(self) -> int:         return self._duration


# ────────────────────────────────────────────────────────── External
class ExternalBackend(AbstractPlaybackBackend):
    """Hands off to an installed player (mpv/vlc/xdg-open). No position feedback —
    the service degrades to 'mark watched on process exit'."""
    backend_id = "external"
    backend_name = "External player"

    CANDIDATES = ("mpv", "vlc", "xdg-open")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc: subprocess.Popen | None = None
        self._label = QLabel("Playing in external player…")
        self._label.setStyleSheet("background:#000;color:#ccc;padding:20px")
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)

    @classmethod
    def descriptor(cls) -> BackendDescriptor:
        found = next((c for c in cls.CANDIDATES if shutil.which(c)), None)
        reason = "" if found else "no external player found (mpv/vlc/xdg-open)"
        return BackendDescriptor(cls.backend_id, cls.backend_name, bool(found), reason)

    def video_widget(self) -> QWidget:
        return self._label

    def open_media(self, path: str, start_seconds: int = 0) -> None:
        for candidate in self.CANDIDATES:
            if shutil.which(candidate):
                self._proc = subprocess.Popen([candidate, path])
                return
        self.errorOccurred.emit("no external player available")

    def _poll(self) -> None:
        if self._proc and self._proc.poll() is not None:
            self._timer.stop()
            self.finished.emit()

    def play(self) -> None:
        self._timer.start()
        self.playingChanged.emit(True)

    # external process owns its controls — these are honest no-ops
    def pause(self) -> None: pass
    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
    def seek_s(self, s: int) -> None: pass
    def set_speed(self, speed: float) -> None: pass
    def set_volume(self, percent: int) -> None: pass
    def is_playing(self) -> bool: return bool(self._proc and self._proc.poll() is None)
    def position_s(self) -> int: return 0
    def duration_s(self) -> int: return 0
