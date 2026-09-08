"""Playback service — Qt-free session logic: payloads, resume, history, autoplay-next.
The PlayerScreen drives a backend; this decides *what* happens with the data."""
from __future__ import annotations

import time
from typing import Any

from app.config.settings import Settings
from app.database.repositories import (
    EpisodeRepository,
    HistoryRepository,
    LibraryStateRepository,
    ProgressRepository,
)
from app.domain.enums import media_key_episode, media_key_movie
from app.domain.events import EventBus
from app.domain.models import PlaybackPayload

PERSIST_EVERY_S = 5


def now_ms() -> int:
    return int(time.time() * 1000)


class PlaybackService:
    def __init__(self, state_repo: LibraryStateRepository, episode_repo: EpisodeRepository,
                 progress_repo: ProgressRepository, history_repo: HistoryRepository,
                 settings: Settings, bus: EventBus):
        self.state = state_repo
        self.episodes = episode_repo
        self.progress = progress_repo
        self.history = history_repo
        self.settings = settings
        self.bus = bus
        self.current: PlaybackPayload | None = None
        self.started_at = 0
        self._last_persist = 0.0

    # ------------------------------------------------------------ payloads
    def payload_movie(self, media: dict[str, Any]) -> PlaybackPayload:
        return PlaybackPayload(
            media_key=media_key_movie(media["id"]),
            title=media["title"],
            subtitle=f"{media.get('year') or ''} · {media.get('runtime_min', 0)} min",
            file_path=media.get("file_path"),
            duration_s=int(media.get("runtime_min") or 0) * 60,
            media_id=media["id"],
        )

    def payload_episode(self, show: dict[str, Any], episode: dict[str, Any]) -> PlaybackPayload:
        return PlaybackPayload(
            media_key=media_key_episode(episode["id"]),
            title=show["title"],
            subtitle=f"S{episode['season']} E{episode['number']} · {episode.get('title') or ''}",
            file_path=episode.get("file_path") or show.get("file_path"),
            duration_s=int(episode.get("runtime_min") or show.get("runtime_min") or 0) * 60,
            episode_id=episode["id"], show_id=show["id"],
            season=episode["season"], number=episode["number"],
        )

    def resume_seconds(self, payload: PlaybackPayload) -> int:
        saved = self.progress.get(payload.media_key)
        return int(saved["position_s"]) if saved else 0

    # --------------------------------------------------------- lifecycle
    def session_started(self, payload: PlaybackPayload) -> None:
        # '_at' carries the resume position attached above (see _At helper)
        self.current = payload
        self.started_at = now_ms()
        from app.domain.events import PLAYBACK_STARTED

        self.bus.emit(PLAYBACK_STARTED, key=payload.media_key, title=payload.title)

    def tick(self, position_s: int, duration_s: int) -> None:
        """Throttled progress persistence; screen calls from backend signals."""
        if not self.current:
            return
        if time.time() - self._last_persist < PERSIST_EVERY_S:
            return
        self._last_persist = time.time()
        self.progress.set_position(self.current.media_key, position_s, duration_s)

    def session_stopped(self, position_s: int, duration_s: int) -> None:
        """User closed early — keep resume point if meaningful."""
        from app.domain.events import PLAYBACK_STOPPED

        if self.current and position_s > 30 and duration_s and position_s < duration_s * 0.95:
            self.progress.set_position(self.current.media_key, position_s, duration_s)
        if self.current:
            self.bus.emit(PLAYBACK_STOPPED, key=self.current.media_key)
        self.current = None

    def session_finished(self) -> PlaybackPayload | None:
        """Natural end: mark watched, write history, compute what's next."""
        from app.domain.events import PLAYBACK_FINISHED

        p = self.current
        if not p:
            return None
        self.progress.clear(p.media_key)
        if p.episode_id:
            self.episodes.mark_watched(p.episode_id)
        elif p.media_id:
            self.state.mark_movie_watched(p.media_id, True)
        self.history.add(p.media_key, p.title, p.subtitle, self.started_at, now_ms())
        self.bus.emit(PLAYBACK_FINISHED, key=p.media_key)
        self.current = None
        if self.settings.get(Settings.AUTOPLAY_NEXT) and p.episode_id:
            return self._next_payload(p)
        return None

    def _next_payload(self, finished: PlaybackPayload) -> PlaybackPayload | None:
        assert finished.episode_id is not None
        nxt = self.episodes.next_after(finished.episode_id)
        if not nxt or not nxt.get("file_path"):
            return None
        return PlaybackPayload(
            media_key=media_key_episode(nxt["id"]), title=finished.title,
            subtitle=f"S{nxt['season']} E{nxt['number']} · {nxt.get('title') or ''}",
            file_path=nxt["file_path"], duration_s=int(nxt.get("runtime_min") or 0) * 60,
            episode_id=nxt["id"], show_id=finished.show_id,
            season=nxt["season"], number=nxt["number"],
        )
