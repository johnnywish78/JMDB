"""Playback service: backend selection, sessions, history, resume, watched.

This is the one coherent playback model used by the whole app:
- choose backend (setting + availability + fallback chain),
- start a session (history row),
- delegate control to the backend,
- persist resume positions,
- mark watched on completion.
"""
from __future__ import annotations

import logging

from app.config.settings import SettingsService
from app.database.repositories import Repositories
from app.domain.events import (
    EventBus,
    PlaybackFinished,
    PlaybackStarted,
    PlaybackStopped,
)
from app.domain.value_objects import PlayableItem
from app.playback.backends.base import BackendCallbacks, PlaybackBackend
from app.playback.backends.external import ExternalBackend
from app.playback.history import HistoryService
from app.playback.resume import ResumeService
from app.playback.session import PlaybackSession

logger = logging.getLogger(__name__)

BACKEND_CLASSES = {}  # populated in _load_backends to guard imports


def _load_backends() -> dict[str, type]:
    global BACKEND_CLASSES
    if BACKEND_CLASSES:
        return BACKEND_CLASSES
    from app.playback.backends.vlc import VlcBackend
    from app.playback.backends.mpv import MpvBackend
    from app.playback.backends.qt import QtBackend

    BACKEND_CLASSES = {
        "vlc": VlcBackend,
        "mpv": MpvBackend,
        "qt": QtBackend,
        "external": ExternalBackend,
    }
    return BACKEND_CLASSES


class NoBackendAvailable(Exception):
    pass


class PlaybackService:
    def __init__(self, repos: Repositories, settings: SettingsService, events: EventBus) -> None:
        self.repos = repos
        self.settings = settings
        self.events = events
        self.history = HistoryService(repos)
        self.resume = ResumeService(repos, settings)
        self._session: PlaybackSession | None = None
        self._backend: PlaybackBackend | None = None

    # -- backend selection ------------------------------------------------------
    def backend_availability(self) -> dict[str, dict]:
        out = {}
        for backend_id, cls in _load_backends().items():
            try:
                available, reason = cls.probe()
            except Exception as exc:
                available, reason = False, str(exc)
            out[backend_id] = {"available": available, "reason": reason, "name": cls.name}
        return out

    def resolve_backend(self) -> tuple[str, str]:
        """Returns (backend_id, description). Raises NoBackendAvailable."""
        availability = self.backend_availability()
        preferred = str(self.settings.get("playback_backend"))
        if preferred != "auto" and availability.get(preferred, {}).get("available"):
            return preferred, availability[preferred]["name"]
        if preferred != "auto":
            logger.warning(
                "preferred backend %s unavailable (%s); falling back",
                preferred, availability.get(preferred, {}).get("reason"),
            )
        for candidate in ("vlc", "mpv", "qt", "external"):
            if availability.get(candidate, {}).get("available"):
                return candidate, availability[candidate]["name"]
        raise NoBackendAvailable(
            "No playback backend available. Install VLC or MPV (recommended), "
            "or PyQt6-Multimedia, or configure an external player in Settings."
        )

    # -- playback control -----------------------------------------------------------
    def start_session(
        self,
        item: PlayableItem,
        profile_id: int,
        backend_id: str | None = None,
        queue: list[PlayableItem] | None = None,
    ) -> PlaybackSession:
        backend_id = backend_id or self.resolve_backend()[0]
        session = PlaybackSession(
            item=item, profile_id=profile_id, queue=queue or [], queue_index=0
        )
        if queue:
            session.queue_index = max(
                i for i, queued in enumerate(queue) if queued.path == item.path
            ) if item.path in [q.path for q in queue] else 0

        resume_pos = self.resume.resume_position(profile_id, item.media_type, item.media_id)
        session.resumed = resume_pos is not None
        session.start_position = resume_pos or 0.0

        session.history_id = self.history.start(
            profile_id, item.media_type, item.media_id, item.media_file_id
        )
        self._session = session
        self.events.publish(
            PlaybackStarted(
                media_type=item.media_type, media_id=item.media_id,
                media_file_id=item.media_file_id, path=item.path, resumed=session.resumed,
            )
        )
        return session

    def attach_backend(self, backend: PlaybackBackend) -> None:
        self._backend = backend

    @property
    def session(self) -> PlaybackSession | None:
        return self._session

    @property
    def backend(self) -> PlaybackBackend | None:
        return self._backend

    # -- session lifecycle (called by the controller) ------------------------------------
    def save_progress(self, position: float, duration: float) -> None:
        if self._session is None:
            return
        self._session.position_seconds = position
        self._session.duration_seconds = duration
        self.resume.save(
            self._session.profile_id,
            self._session.current.media_type,
            self._session.current.media_id,
            position,
            duration,
            self._session.current.media_file_id,
        )

    def finish_session(self, position: float, duration: float, completed: bool) -> None:
        if self._session is None:
            return
        session = self._session
        if session.history_id is not None:
            self.history.finish(session.history_id, position, duration, completed)
        if completed:
            self.repos.playback.mark_watched(
                session.profile_id, session.current.media_type, session.current.media_id
            )
            self.resume.clear(session.profile_id, session.current.media_type, session.current.media_id)
            self.events.publish(
                PlaybackFinished(
                    media_type=session.current.media_type,
                    media_id=session.current.media_id,
                )
            )
        self.events.publish(
            PlaybackStopped(
                media_type=session.current.media_type,
                media_id=session.current.media_id,
                position_seconds=position,
                duration_seconds=duration,
                completed=completed,
            )
        )
        self._session = None

    # -- watched marking (manual, from UI) -------------------------------------------------
    def mark_watched(self, profile_id: int, media_type: str, media_id: int) -> None:
        self.repos.playback.mark_watched(profile_id, media_type, media_id)

    def mark_unwatched(self, profile_id: int, media_type: str, media_id: int) -> None:
        self.repos.playback.mark_unwatched(profile_id, media_type, media_id)

    def mark_season_watched(self, profile_id: int, season_id: int) -> int:
        episodes = self.repos.tv.episodes_for_season(season_id, profile_id)
        for episode in episodes:
            self.mark_watched(profile_id, "episode", episode["id"])
        return len(episodes)

    def mark_show_watched(self, profile_id: int, tv_show_id: int) -> int:
        count = 0
        for season in self.repos.tv.seasons_for_show(tv_show_id, profile_id):
            count += self.mark_season_watched(profile_id, season["id"])
        return count

    # -- external player path --------------------------------------------------------------
    def play_external(self, item: PlayableItem, profile_id: int) -> bool:
        """Open in an external player; returns True when launched."""
        session = self.start_session(item, profile_id, backend_id="external")
        backend = ExternalBackend(
            configured_path=str(self.settings.get("external_player_path"))
        )
        resume_pos = session.start_position
        process = backend.launch(item, resume_pos)
        if process is None:
            return False
        # record an honest session: launched externally, position unknown
        self.finish_session(
            position=0.0, duration=0.0, completed=False
        )
        return True
