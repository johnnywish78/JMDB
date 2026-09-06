"""Favorites, watchlist, ratings, watched state (user lists per profile)."""
from __future__ import annotations

from app.domain.models import Favorite, UserRating, WatchlistItem
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses


class UserListsRepository(BaseRepository):
    # -- favorites -----------------------------------------------------------
    def is_favorite(self, profile_id: int, media_type: str, media_id: int) -> bool:
        return bool(
            self.db.scalar(
                "SELECT 1 FROM favorites WHERE profile_id=? AND media_type=? AND media_id=?",
                (profile_id, media_type, media_id),
            )
        )

    def set_favorite(self, profile_id: int, media_type: str, media_id: int, value: bool) -> None:
        if value:
            self.db.execute(
                "INSERT OR IGNORE INTO favorites (profile_id, media_type, media_id) VALUES (?,?,?)",
                (profile_id, media_type, media_id),
            )
        else:
            self.db.execute(
                "DELETE FROM favorites WHERE profile_id=? AND media_type=? AND media_id=?",
                (profile_id, media_type, media_id),
            )

    def toggle_favorite(self, profile_id: int, media_type: str, media_id: int) -> bool:
        value = not self.is_favorite(profile_id, media_type, media_id)
        self.set_favorite(profile_id, media_type, media_id, value)
        return value

    def favorites(self, profile_id: int, media_type: str | None = None) -> list[dict]:
        """Favorites joined to display titles/posters."""
        where = ["f.profile_id=?"]
        params: list = [profile_id]
        if media_type:
            where.append("f.media_type=?")
            params.append(media_type)
        rows = self.db.query(
            "SELECT f.media_type, f.media_id, f.created_at,"
            " CASE f.media_type"
            "  WHEN 'movie' THEN (SELECT m.title FROM movies m WHERE m.id=f.media_id)"
            "  WHEN 'tv_show' THEN (SELECT s.title FROM tv_shows s WHERE s.id=f.media_id)"
            "  WHEN 'artist' THEN (SELECT a.name FROM music_artists a WHERE a.id=f.media_id)"
            "  WHEN 'album' THEN (SELECT al.title FROM music_albums al WHERE al.id=f.media_id)"
            "  WHEN 'track' THEN (SELECT t.title FROM music_tracks t WHERE t.id=f.media_id)"
            "  WHEN 'episode' THEN (SELECT s2.title||' '||e.season_number||'x'||e.episode_number"
            "      FROM episodes e JOIN tv_shows s2 ON s2.id=e.tv_show_id WHERE e.id=f.media_id)"
            " END AS title,"
            " CASE f.media_type"
            "  WHEN 'movie' THEN (SELECT m.year FROM movies m WHERE m.id=f.media_id)"
            "  WHEN 'tv_show' THEN (SELECT substr(s.first_air_date,1,4) FROM tv_shows s WHERE s.id=f.media_id)"
            "  WHEN 'album' THEN (SELECT al.year FROM music_albums al WHERE al.id=f.media_id)"
            " END AS year,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type=f.media_type AND a.owner_id=f.media_id"
            "  AND a.kind IN ('poster','album_cover','season_poster') AND a.local_path<>'' LIMIT 1) AS poster_path"
            " FROM favorites f WHERE " + " AND ".join(where) +
            " ORDER BY f.created_at DESC",
            params,
        )
        return [dict(r) for r in rows if r["title"]]

    # -- watchlist ---------------------------------------------------------------
    def in_watchlist(self, profile_id: int, media_type: str, media_id: int) -> bool:
        return bool(
            self.db.scalar(
                "SELECT 1 FROM watchlist WHERE profile_id=? AND media_type=? AND media_id=?",
                (profile_id, media_type, media_id),
            )
        )

    def set_watchlist(self, profile_id: int, media_type: str, media_id: int, value: bool) -> None:
        if value:
            self.db.execute(
                "INSERT OR IGNORE INTO watchlist (profile_id, media_type, media_id) VALUES (?,?,?)",
                (profile_id, media_type, media_id),
            )
        else:
            self.db.execute(
                "DELETE FROM watchlist WHERE profile_id=? AND media_type=? AND media_id=?",
                (profile_id, media_type, media_id),
            )

    def toggle_watchlist(self, profile_id: int, media_type: str, media_id: int) -> bool:
        value = not self.in_watchlist(profile_id, media_type, media_id)
        self.set_watchlist(profile_id, media_type, media_id, value)
        return value

    def watchlist(self, profile_id: int, media_type: str | None = None) -> list[dict]:
        where = ["w.profile_id=?"]
        params: list = [profile_id]
        if media_type:
            where.append("w.media_type=?")
            params.append(media_type)
        rows = self.db.query(
            "SELECT w.media_type, w.media_id, w.added_at,"
            " CASE w.media_type"
            "  WHEN 'movie' THEN (SELECT m.title FROM movies m WHERE m.id=w.media_id)"
            "  WHEN 'tv_show' THEN (SELECT s.title FROM tv_shows s WHERE s.id=w.media_id)"
            "  WHEN 'artist' THEN (SELECT a.name FROM music_artists a WHERE a.id=w.media_id)"
            "  WHEN 'album' THEN (SELECT al.title FROM music_albums al WHERE al.id=w.media_id)"
            " END AS title,"
            " CASE w.media_type"
            "  WHEN 'movie' THEN (SELECT m.year FROM movies m WHERE m.id=w.media_id)"
            "  WHEN 'tv_show' THEN (SELECT substr(s.first_air_date,1,4) FROM tv_shows s WHERE s.id=w.media_id)"
            "  WHEN 'album' THEN (SELECT al.year FROM music_albums al WHERE al.id=w.media_id)"
            " END AS year,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type=w.media_type AND a.owner_id=w.media_id"
            "  AND a.kind IN ('poster','album_cover') AND a.local_path<>'' LIMIT 1) AS poster_path"
            " FROM watchlist w WHERE " + " AND ".join(where) +
            " ORDER BY w.added_at DESC",
            params,
        )
        return [dict(r) for r in rows if r["title"]]

    # -- ratings --------------------------------------------------------------------
    def get_rating(self, profile_id: int, media_type: str, media_id: int) -> float | None:
        value = self.db.scalar(
            "SELECT rating FROM user_ratings WHERE profile_id=? AND media_type=? AND media_id=?",
            (profile_id, media_type, media_id),
        )
        return float(value) if value is not None else None

    def set_rating(self, profile_id: int, media_type: str, media_id: int, rating: float | None) -> None:
        if rating is None or rating <= 0:
            self.db.execute(
                "DELETE FROM user_ratings WHERE profile_id=? AND media_type=? AND media_id=?",
                (profile_id, media_type, media_id),
            )
            return
        self.db.execute(
            "INSERT INTO user_ratings (profile_id, media_type, media_id, rating, rated_at)"
            " VALUES (?,?,?,?,datetime('now'))"
            " ON CONFLICT(profile_id, media_type, media_id)"
            " DO UPDATE SET rating=excluded.rating, rated_at=excluded.rated_at",
            (profile_id, media_type, media_id, float(rating)),
        )

    def favorite_count(self, profile_id: int) -> int:
        return int(
            self.db.scalar("SELECT COUNT(*) FROM favorites WHERE profile_id=?", (profile_id,)) or 0
        )

    def watchlist_count(self, profile_id: int) -> int:
        return int(
            self.db.scalar("SELECT COUNT(*) FROM watchlist WHERE profile_id=?", (profile_id,)) or 0
        )
