"""Playback history recording."""
from __future__ import annotations

from app.database.repositories import Repositories


class HistoryService:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def start(self, profile_id: int, media_type: str, media_id: int, media_file_id: int | None) -> int:
        return self.repos.playback.start_session(profile_id, media_type, media_id, media_file_id)

    def finish(self, history_id: int, position: float, duration: float, completed: bool) -> None:
        self.repos.playback.finish_session(history_id, position, duration, completed)

    def list(self, profile_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
        return self.repos.playback.history(profile_id, limit, offset)

    def recently_played(self, profile_id: int, limit: int = 20) -> list[dict]:
        return self.repos.playback.recently_played(profile_id, limit)
