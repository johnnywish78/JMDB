"""Resume position management."""
from __future__ import annotations

from app.config.settings import SettingsService
from app.database.repositories import Repositories


class ResumeService:
    def __init__(self, repos: Repositories, settings: SettingsService) -> None:
        self.repos = repos
        self.settings = settings

    def save(self, profile_id: int, media_type: str, media_id: int,
             position: float, duration: float, media_file_id: int | None = None) -> None:
        if position <= 0:
            return
        self.repos.playback.save_position(
            profile_id, media_type, media_id, position, duration, media_file_id
        )

    def resume_position(self, profile_id: int, media_type: str, media_id: int) -> float | None:
        """Position to resume from, or None when starting fresh is right."""
        state = self.repos.playback.get_position(profile_id, media_type, media_id)
        if state is None:
            return None
        min_seconds = float(self.settings.get("resume_min_seconds"))
        completion = float(self.settings.get("resume_completion_pct")) / 100.0
        if state.position_seconds < min_seconds:
            return None
        if state.duration_seconds > 0 and state.position_seconds / state.duration_seconds >= completion:
            return None  # effectively finished: start over
        return state.position_seconds

    def clear(self, profile_id: int, media_type: str, media_id: int) -> None:
        self.repos.playback.clear_position(profile_id, media_type, media_id)

    def continue_watching(self, profile_id: int, limit: int = 20) -> list[dict]:
        return self.repos.playback.continue_watching(profile_id, limit)
