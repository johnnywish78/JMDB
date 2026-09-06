"""TV shows, seasons, episodes repository."""
from __future__ import annotations

from typing import Any

from app.domain.models import Episode, Season, TvShow
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses

POSTER_SUB = (
    "(SELECT a.local_path FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id"
    " AND a.kind='poster' AND a.local_path<>'' ORDER BY a.id LIMIT 1) AS poster_path"
)
BACKDROP_SUB = (
    "(SELECT a.local_path FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id"
    " AND a.kind='backdrop' AND a.local_path<>'' ORDER BY a.id LIMIT 1) AS backdrop_path"
)

EP_WATCHED = (
    "EXISTS (SELECT 1 FROM playback_history h WHERE h.profile_id=? AND h.media_type='episode'"
    " AND h.media_id=e.id AND h.completed=1)"
)


class TvRepository(BaseRepository):
    # -- shows ----------------------------------------------------------------
    def get_show(self, show_id: int) -> TvShow | None:
        row = self.db.query_one("SELECT * FROM tv_shows WHERE id=?", (show_id,))
        return row_to_dataclass(row, TvShow) if row else None

    def find_show_by_title(self, title: str) -> TvShow | None:
        row = self.db.query_one(
            "SELECT * FROM tv_shows WHERE lower(title)=lower(?) OR lower(original_title)=lower(?) LIMIT 1",
            (title, title),
        )
        return row_to_dataclass(row, TvShow) if row else None

    def create_show(self, show: TvShow) -> int:
        cur = self.db.execute(
            "INSERT INTO tv_shows (title, original_title, sort_title, first_air_date,"
            " last_air_date, status, overview, rating, vote_count)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                show.title, show.original_title, show.sort_title, show.first_air_date,
                show.last_air_date, show.status, show.overview, show.rating, show.vote_count,
            ),
        )
        return int(cur.lastrowid)

    def update_show(self, show_id: int, values: dict[str, Any]) -> None:
        allowed = {
            "title", "original_title", "sort_title", "first_air_date", "last_air_date",
            "status", "overview", "rating", "vote_count",
        }
        sets, params = [], []
        for key, value in values.items():
            if key in allowed:
                sets.append(f"{key}=?")
                params.append(value)
        if not sets:
            return
        params.append(show_id)
        self.db.execute(
            f"UPDATE tv_shows SET {', '.join(sets)}, updated_at=datetime('now') WHERE id=?",
            params,
        )

    def delete_show(self, show_id: int) -> None:
        self.db.execute("DELETE FROM tv_shows WHERE id=?", (show_id,))

    def count_shows(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM tv_shows") or 0)

    def list_shows(
        self,
        profile_id: int,
        page: int = 0,
        per_page: int = 60,
        genre: str = "",
        query: str = "",
        sort: str = "title",
        favorites_only: bool = False,
        watchlist_only: bool = False,
        unwatched_only: bool = False,
    ) -> tuple[list[dict], int]:
        where, params = ["1=1"], []
        if genre:
            where.append(
                "s.id IN (SELECT mg.media_id FROM media_genres mg JOIN genres g ON g.id=mg.genre_id"
                " WHERE mg.media_type='tv_show' AND g.name=?)"
            )
            params.append(genre)
        if query:
            where.append("(s.title LIKE ? OR s.original_title LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if favorites_only:
            where.append("EXISTS (SELECT 1 FROM favorites f WHERE f.profile_id=? AND f.media_type='tv_show' AND f.media_id=s.id)")
            params.append(profile_id)
        if watchlist_only:
            where.append("EXISTS (SELECT 1 FROM watchlist w WHERE w.profile_id=? AND w.media_type='tv_show' AND w.media_id=s.id)")
            params.append(profile_id)
        if unwatched_only:
            where.append(
                "EXISTS (SELECT 1 FROM episodes e WHERE e.tv_show_id=s.id AND NOT " + EP_WATCHED.replace("e.id", "e.id") + ")"
            )
            params.append(profile_id)
        order = {
            "title": "s.sort_title COLLATE NOCASE, s.title COLLATE NOCASE",
            "added": "s.added_at DESC",
            "rating": "s.rating DESC",
        }.get(sort, "s.sort_title COLLATE NOCASE")
        base_where = " AND ".join(where)
        total = int(self.db.scalar(f"SELECT COUNT(*) FROM tv_shows s WHERE {base_where}", params) or 0)
        rows = self.db.query(
            "SELECT s.id, s.title, s.first_air_date, s.rating, s.status,"
            " (SELECT COUNT(DISTINCT e.season_number) FROM episodes e WHERE e.tv_show_id=s.id) AS season_count,"
            " (SELECT COUNT(*) FROM episodes e WHERE e.tv_show_id=s.id) AS episode_count,"
            f" {POSTER_SUB},"
            " EXISTS (SELECT 1 FROM favorites f WHERE f.profile_id=? AND f.media_type='tv_show' AND f.media_id=s.id) AS is_favorite,"
            " EXISTS (SELECT 1 FROM watchlist w WHERE w.profile_id=? AND w.media_type='tv_show' AND w.media_id=s.id) AS in_watchlist"
            f" FROM tv_shows s WHERE {base_where} ORDER BY {order} LIMIT ? OFFSET ?",
            [profile_id, profile_id, *params, per_page, page * per_page],
        )
        return [dict(r) for r in rows], total

    # -- seasons -----------------------------------------------------------------
    def get_season(self, season_id: int) -> Season | None:
        row = self.db.query_one("SELECT * FROM seasons WHERE id=?", (season_id,))
        return row_to_dataclass(row, Season) if row else None

    def get_or_create_season(self, tv_show_id: int, season_number: int) -> int:
        row = self.db.query_one(
            "SELECT id FROM seasons WHERE tv_show_id=? AND season_number=?",
            (tv_show_id, season_number),
        )
        if row:
            return int(row["id"])
        cur = self.db.execute(
            "INSERT INTO seasons (tv_show_id, season_number) VALUES (?,?)",
            (tv_show_id, season_number),
        )
        return int(cur.lastrowid)

    def update_season(self, season_id: int, values: dict[str, Any]) -> None:
        allowed = {"title", "overview", "air_date"}
        sets, params = [], []
        for key, value in values.items():
            if key in allowed:
                sets.append(f"{key}=?")
                params.append(value)
        if sets:
            params.append(season_id)
            self.db.execute(f"UPDATE seasons SET {', '.join(sets)} WHERE id=?", params)

    def seasons_for_show(self, tv_show_id: int, profile_id: int) -> list[dict]:
        rows = self.db.query(
            "SELECT se.id, se.season_number, se.title, se.overview, se.air_date,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type='season' AND a.owner_id=se.id"
            "  AND a.kind='season_poster' AND a.local_path<>'' LIMIT 1) AS poster_path,"
            " (SELECT COUNT(*) FROM episodes e WHERE e.season_id=se.id) AS episode_count,"
            " (SELECT COUNT(*) FROM episodes e WHERE e.season_id=se.id AND " + EP_WATCHED + ") AS watched_count"
            " FROM seasons se WHERE se.tv_show_id=? ORDER BY se.season_number",
            (profile_id, tv_show_id),
        )
        return [dict(r) for r in rows]

    # -- episodes -------------------------------------------------------------------
    def get_episode(self, episode_id: int) -> Episode | None:
        row = self.db.query_one("SELECT * FROM episodes WHERE id=?", (episode_id,))
        return row_to_dataclass(row, Episode) if row else None

    def get_or_create_episode(
        self, tv_show_id: int, season_id: int, season_number: int, episode_number: int
    ) -> tuple[int, bool]:
        row = self.db.query_one(
            "SELECT id FROM episodes WHERE season_id=? AND episode_number=?",
            (season_id, episode_number),
        )
        if row:
            return int(row["id"]), False
        cur = self.db.execute(
            "INSERT INTO episodes (tv_show_id, season_id, season_number, episode_number)"
            " VALUES (?,?,?,?)",
            (tv_show_id, season_id, season_number, episode_number),
        )
        return int(cur.lastrowid), True

    def update_episode(self, episode_id: int, values: dict[str, Any]) -> None:
        allowed = {"title", "overview", "air_date", "runtime_seconds", "rating"}
        sets, params = [], []
        for key, value in values.items():
            if key in allowed:
                sets.append(f"{key}=?")
                params.append(value)
        if sets:
            params.append(episode_id)
            self.db.execute(f"UPDATE episodes SET {', '.join(sets)} WHERE id=?", params)

    def episodes_for_season(self, season_id: int, profile_id: int) -> list[dict]:
        rows = self.db.query(
            "SELECT e.id, e.episode_number, e.season_number, e.title, e.overview, e.air_date,"
            " e.runtime_seconds, e.rating, e.tv_show_id,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type='episode' AND a.owner_id=e.id"
            "  AND a.kind='still' AND a.local_path<>'' LIMIT 1) AS still_path,"
            " (SELECT f.path FROM media_file_links l JOIN media_files f ON f.id=l.media_file_id"
            "  WHERE l.media_item_type='episode' AND l.media_item_id=e.id AND f.is_missing=0"
            "  ORDER BY l.is_primary DESC LIMIT 1) AS file_path,"
            f" {EP_WATCHED} AS watched,"
            " (SELECT ps.position_seconds FROM playback_state ps WHERE ps.profile_id=?"
            "  AND ps.media_type='episode' AND ps.media_id=e.id) AS position_seconds,"
            " (SELECT ps.duration_seconds FROM playback_state ps WHERE ps.profile_id=?"
            "  AND ps.media_type='episode' AND ps.media_id=e.id) AS duration_seconds"
            " FROM episodes e WHERE e.season_id=? ORDER BY e.episode_number",
            (profile_id, profile_id, profile_id, season_id),
        )
        return [dict(r) for r in rows]

    def episode_details(self, episode_id: int, profile_id: int) -> dict | None:
        rows = self.db.query(
            "SELECT e.id, e.episode_number, e.season_number, e.title, e.overview, e.air_date,"
            " e.runtime_seconds, e.rating, e.tv_show_id, e.season_id,"
            " (SELECT s.title FROM tv_shows s WHERE s.id=e.tv_show_id) AS show_title,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type='episode' AND a.owner_id=e.id"
            "  AND a.kind='still' AND a.local_path<>'' LIMIT 1) AS still_path,"
            " (SELECT a2.local_path FROM artwork a2 WHERE a2.owner_type='tv_show' AND a2.owner_id=e.tv_show_id"
            "  AND a2.kind='poster' AND a2.local_path<>'' LIMIT 1) AS poster_path,"
            " (SELECT f.path FROM media_file_links l JOIN media_files f ON f.id=l.media_file_id"
            "  WHERE l.media_item_type='episode' AND l.media_item_id=e.id AND f.is_missing=0"
            "  ORDER BY l.is_primary DESC LIMIT 1) AS file_path,"
            f" {EP_WATCHED} AS watched,"
            " (SELECT ps.position_seconds FROM playback_state ps WHERE ps.profile_id=?"
            "  AND ps.media_type='episode' AND ps.media_id=e.id) AS position_seconds,"
            " (SELECT ps.duration_seconds FROM playback_state ps WHERE ps.profile_id=?"
            "  AND ps.media_type='episode' AND ps.media_id=e.id) AS duration_seconds"
            " FROM episodes e WHERE e.id=?",
            (profile_id, profile_id, profile_id, episode_id),
        )
        return dict(rows[0]) if rows else None

    def recent_episodes(self, profile_id: int, limit: int = 20) -> list[dict]:
        rows = self.db.query(
            "SELECT e.id, e.title, e.episode_number, e.season_number, e.tv_show_id,"
            " (SELECT s.title FROM tv_shows s WHERE s.id=e.tv_show_id) AS show_title,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type='episode' AND a.owner_id=e.id"
            "  AND a.kind='still' AND a.local_path<>'' LIMIT 1) AS still_path,"
            " (SELECT a2.local_path FROM artwork a2 WHERE a2.owner_type='tv_show' AND a2.owner_id=e.tv_show_id"
            "  AND a2.kind='poster' AND a2.local_path<>'' LIMIT 1) AS poster_path,"
            " MAX(mf.indexed_at) AS added_at"
            " FROM episodes e"
            " JOIN media_file_links l ON l.media_item_type='episode' AND l.media_item_id=e.id"
            " JOIN media_files mf ON mf.id=l.media_file_id AND mf.is_missing=0"
            " GROUP BY e.id ORDER BY added_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    def count_episodes(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM episodes") or 0)

    def count_seasons(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM seasons") or 0)

    def episodes_needing_metadata(self, show_limit: int = 20) -> list[int]:
        rows = self.db.query(
            "SELECT e.id FROM episodes e WHERE e.title='' ORDER BY e.id LIMIT ?", (show_limit,)
        )
        return [r["id"] for r in rows]

    def unwatched_episode_ids(self, tv_show_id: int, profile_id: int) -> list[int]:
        rows = self.db.query(
            "SELECT e.id FROM episodes e WHERE e.tv_show_id=? AND NOT " + EP_WATCHED
            + " ORDER BY e.season_number, e.episode_number",
            (profile_id, tv_show_id),
        )
        return [r["id"] for r in rows]

    def next_episode(self, tv_show_id: int, profile_id: int) -> dict | None:
        """First unwatched episode ordered by season/episode, with file."""
        rows = self.db.query(
            "SELECT e.id, e.season_id, e.title, e.episode_number, e.season_number,"
            " (SELECT s.title FROM tv_shows s WHERE s.id=e.tv_show_id) AS show_title,"
            " (SELECT f.path FROM media_file_links l JOIN media_files f ON f.id=l.media_file_id"
            "  WHERE l.media_item_type='episode' AND l.media_item_id=e.id AND f.is_missing=0"
            "  ORDER BY l.is_primary DESC LIMIT 1) AS file_path"
            " FROM episodes e WHERE e.tv_show_id=? AND NOT " + EP_WATCHED
            + " ORDER BY e.season_number, e.episode_number LIMIT 1",
            (profile_id, tv_show_id),
        )
        return dict(rows[0]) if rows else None
