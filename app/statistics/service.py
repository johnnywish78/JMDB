"""Real statistics derived from library + playback data."""
from __future__ import annotations

from app.database.repositories import Repositories


class StatisticsService:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def overview(self, profile_id: int) -> dict:
        watched = self.repos.playback.watched_counts(profile_id)
        return {
            "movies": self.repos.movies.count(),
            "tv_shows": self.repos.tv.count_shows(),
            "seasons": self.repos.tv.count_seasons(),
            "episodes": self.repos.tv.count_episodes(),
            "artists": self.repos.music.count_artists(),
            "albums": self.repos.music.count_albums(),
            "tracks": self.repos.music.count_tracks(),
            "people": self.repos.people.count(),
            "files": self.repos.files.count(),
            "missing_files": self.repos.files.count(missing=True),
            "watched_movies": watched.get("movie", 0),
            "watched_episodes": watched.get("episode", 0),
            "watched_tracks": watched.get("track", 0),
            "unwatched_movies": max(0, self.repos.movies.count() - watched.get("movie", 0)),
            "watch_seconds": self.repos.playback.total_watch_seconds(profile_id),
            "favorite_count": self.repos.lists.favorite_count(profile_id),
            "watchlist_count": self.repos.lists.watchlist_count(profile_id),
            "playback_sessions": self.repos.playback.history_count(profile_id),
            "artwork_cached": self.repos.artwork.cached_count(),
        }

    def top_genres(self, limit: int = 10) -> list[tuple[str, int]]:
        return self.repos.taxonomy.genre_counts()[:limit]

    def top_people(self, role: str = "actor", limit: int = 10) -> list[tuple[str, int]]:
        return self.repos.people.top_people(role, limit)

    def recently_added(self, profile_id: int, limit: int = 10) -> list[dict]:
        return self.repos.movies.recently_added(profile_id, limit)

    def recently_played(self, profile_id: int, limit: int = 10) -> list[dict]:
        return self.repos.playback.recently_played(profile_id, limit)

    def watch_time_by_month(self, profile_id: int, months: int = 12) -> list[tuple[str, float]]:
        rows = self.repos.db.query(
            """SELECT substr(started_at, 1, 7) AS month, SUM(position_seconds) AS seconds
            FROM playback_history WHERE profile_id=?
            GROUP BY month ORDER BY month DESC LIMIT ?""",
            (profile_id, months),
        )
        return [(r["month"], float(r["seconds"] or 0)) for r in reversed(rows)]
