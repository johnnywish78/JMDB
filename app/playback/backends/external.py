"""External player fallback backend.

Launches a system player (VLC, MPV, ffplay, mplayer, or the desktop
default) as a separate process. Honest limitations: no embedded video, no
position feedback, no in-app controls — JMDB records the session, passes a
resume position via CLI flags when the player supports it, and the user
marks watched manually or via the player itself.
"""
from __future__ import annotations

import logging
import shlex
import shutil
import subprocess

from app.domain.value_objects import PlayableItem
from app.playback.backends.base import (
    BackendCallbacks,
    Capabilities,
    PlaybackBackend,
    PlaybackError,
)

logger = logging.getLogger(__name__)

CANDIDATES = ["vlc", "mpv", "ffplay", "mplayer", "totem", "xdg-open"]


class ExternalBackend(PlaybackBackend):
    id = "external"
    name = "External player"
    capabilities = Capabilities(embed=False, pause=False, seek=False)

    @staticmethod
    def detect_player(configured_path: str = "") -> tuple[str, str]:
        """(player_kind, executable). Detects real binaries, never hard-codes paths."""
        if configured_path:
            if shutil.which(configured_path) or (
                "/" in configured_path and shutil.which(shlex.split(configured_path)[0])
            ):
                return "custom", configured_path
        for candidate in CANDIDATES:
            path = shutil.which(candidate)
            if path:
                return candidate, path
        return "", ""

    @staticmethod
    def probe() -> tuple[bool, str]:
        kind, path = ExternalBackend.detect_player()
        if kind:
            return True, ""
        return False, "no external player found (vlc, mpv, ffplay, mplayer, or xdg-open)"

    def __init__(self, callbacks: BackendCallbacks | None = None, configured_path: str = "") -> None:
        super().__init__(callbacks)
        self._configured_path = configured_path
        self._process: subprocess.Popen | None = None
        self._state = "idle"
        self._kind, self._exe = self.detect_player(configured_path)

    @property
    def player_kind(self) -> str:
        return self._kind

    # -- lifecycle -------------------------------------------------------------
    def launch(self, item: PlayableItem, start_position: float = 0.0) -> subprocess.Popen:
        """Launch the external player for a playable item."""
        if not self._exe:
            raise PlaybackError(
                "No external media player found. Install VLC or MPV, or configure "
                "an external player command in Settings → Playback."
            )
        args = [self._exe]
        if self._kind == "custom" and " " in self._exe:
            args = shlex.split(self._exe)
        from app.library.probe import safe_start_time_args

        args += safe_start_time_args(self._kind, start_position)
        args.append(item.path)  # verbatim path: spaces/Unicode safe as one argv element
        logger.info("launching external player: %s", shlex.join(args))
        self._process = subprocess.Popen(args)
        self._state = "playing"
        self.callbacks.on_state("playing")
        return self._process

    def load(self, path: str, start_position: float = 0.0) -> None:
        # external backend is driven via launch() with full item context
        raise PlaybackError("use PlaybackService.play(), which calls launch() for external players")

    def play(self) -> None:
        raise PlaybackError("external player cannot be controlled from JMDB")

    def pause(self) -> None:
        raise PlaybackError("external player cannot be controlled from JMDB")

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
        self._state = "stopped"
        self.callbacks.on_state("stopped")

    @property
    def state(self) -> str:
        if self._process is not None and self._process.poll() is not None:
            return "stopped"
        return self._state

    @property
    def position(self) -> float:
        return 0.0

    @property
    def duration(self) -> float:
        return 0.0

    def teardown(self) -> None:
        # never kill the user's player on app exit: only stop on explicit stop()
        self._process = None
