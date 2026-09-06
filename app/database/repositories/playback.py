"""Playback repository: history, resume state, watched state.

One coherent playback model:
- ``playback_history`` rows are the log of playback sessions
  (a completed row is the definition of "watched").
- ``playback_state`` holds the single resume position per item.
"""
from __future__ import annotations

from app.domain.models import PlaybackHistoryEntry, PlaybackState
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses


class PlaybackRepository(BaseRepository):
    # -- history ---------------------------------------------------------------
    def start_session(
        self,
        profile_id: int,
        media_type: str,
        media_id: int,
        media_file_id: int | None,
    ) -> int:
        cur = self.db.execute(
            "INSERT INTO playback_history (profile_id, media_file_id, media_type, media_id)"
            " VALUES (?,?,?,?)",
            (profile_id, media_file_id, media_type, media_id),
        )
        return int(cur.lastrowid)

    def finish_session(
        self,
        history_id: int,
        position_seconds: float,
        duration_seconds: float,
        completed: bool,
    ) -> None:
        self.db.execute(
            "UPDATE playback_history SET finished_at=datetime('now'), position_seconds=?,"
            " duration_seconds=?, completed=? WHERE id=?",
            (position_seconds, duration_seconds, 1 if completed else 0, history_id),
        )

    def history(self, profile_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
        rows = self.db.query(
            "SELECT h.id, h.media_type, h.media_id, h.started_at, h.finished_at,"
            " h.position_seconds, h.duration_seconds, h.completed, h.media_file_id,"
            " CASE h.media_type"
            "  WHEN 'movie' THEN (SELECT m.title FROM movies m WHERE m.id=h.media_id)"
            "  WHEN 'episode' THEN (SELECT s.title||' — S'||e.season_number||'E'||e.episode_number"
            "      FROM episodes e JOIN tv_shows s ON s.id=e.tv_show_id WHERE e.id=h.media_id)"
            "  WHEN 'track' THEN (SELECT t.title FROM music_tracks t WHERE t.id=h.media_id)"
            " END AS title,"
            " CASE h.media_type"
            "  WHEN 'episode' THEN (SELECT s.title FROM episodes e JOIN tv_shows s ON s.id=e.tv_show_id"
            "      WHERE e.id=h.media_id) END AS show_title"
            " FROM playback_history h WHERE h.profile_id=?"
            " ORDER BY h.started_at DESC LIMIT ? OFFSET ?",
            (profile_id, limit, offset),
        )
        return [dict(r) for r in rows if r["title"]]

    def history_count(self, profile_id: int) -> int:
        return int(
            self.db.scalar(
                "SELECT COUNT(*) FROM playback_history WHERE profile_id=?", (profile_id,)
            )
            or 0
        )

    def recently_played(self, profile_id: int, limit: int = 20) -> list[dict]:
        """Most recent session per media item (movies/episodes/tracks)."""
        rows = self.db.query(
            "SELECT h.media_type, h.media_id, MAX(h.started_at) AS last_played,"
            " h.completed,"
            " CASE h.media_type"
            "  WHEN 'movie' THEN (SELECT m.title FROM movies m WHERE m.id=h.media_id)"
            "  WHEN 'episode' THEN (SELECT s.title||' '||e.season_number||'x'||e.episode_number"
            "      FROM episodes e JOIN tv_shows s ON s.id=e.tv_show_id WHERE e.id=h.media_id)"
            "  WHEN 'track' THEN (SELECT t.title FROM music_tracks t WHERE t.id=h.media_id)"
            " END AS title,"
            " CASE h.media_type"
            "  WHEN 'episode' THEN (SELECT s2.title FROM episodes e JOIN tv_shows s2 ON s2.id=e.tv_show_id"
            "      WHERE e.id=h.media_id) END AS show_title,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type=h.media_type AND a.owner_id=h.media_id"
            "  AND a.kind IN ('poster','still','album_cover') AND a.local_path<>'' LIMIT 1) AS poster_path"
            " FROM playback_history h WHERE h.profile_id=?"
            " GROUP BY h.media_type, h.media_id ORDER BY last_played DESC LIMIT ?",
            (profile_id, limit),
        )
        return [dict(r) for r in rows if r["title"]]

    # -- resume state ---------------------------------------------------------------
    def save_position(
        self,
        profile_id: int,
        media_type: str,
        media_id: int,
        position_seconds: float,
        duration_seconds: float,
        media_file_id: int | None = None,
    ) -> None:
        self.db.execute(
            "INSERT INTO playback_state (profile_id, media_type, media_id, media_file_id,"
            " position_seconds, duration_seconds, updated_at)"
            " VALUES (?,?,?,?,?,?,datetime('now'))"
            " ON CONFLICT(profile_id, media_type, media_id) DO UPDATE SET"
            " position_seconds=excluded.position_seconds,"
            " duration_seconds=excluded.duration_seconds,"
            " media_file_id=COALESCE(excluded.media_file_id, media_file_id),"
            " updated_at=excluded.updated_at",
            (profile_id, media_type, media_id, media_file_id, position_seconds, duration_seconds),
        )

    def get_position(self, profile_id: int, media_type: str, media_id: int) -> PlaybackState | None:
        row = self.db.query_one(
            "SELECT * FROM playback_state WHERE profile_id=? AND media_type=? AND media_id=?",
            (profile_id, media_type, media_id),
        )
        return row_to_dataclass(row, PlaybackState) if row else None

    def clear_position(self, profile_id: int, media_type: str, media_id: int) -> None:
        self.db.execute(
            "DELETE FROM playback_state WHERE profile_id=? AND media_type=? AND media_id=?",
            (profile_id, media_type, media_id),
        )

    def continue_watching(self, profile_id: int, limit: int = 20) -> list[dict]:
        """Items with a saved position that are not finished."""
        rows = self.db.query(
            "SELECT ps.media_type, ps.media_id, ps.position_seconds, ps.duration_seconds,"
            " ps.updated_at, ps.media_file_id,"
            " CASE ps.media_type"
            "  WHEN 'movie' THEN (SELECT m.title FROM movies m WHERE m.id=ps.media_id)"
            "  WHEN 'episode' THEN (SELECT s.title||' — S'||e.season_number||'E'||e.episode_number"
            "      FROM episodes e JOIN tv_shows s ON s.id=e.tv_show_id WHERE e.id=ps.media_id)"
            " END AS title,"
            " CASE ps.media_type"
            "  WHEN 'episode' THEN (SELECT s2.title FROM episodes e JOIN tv_shows s2 ON s2.id=e.tv_show_id"
            "      WHERE e.id=ps.media_id) END AS show_title,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type=ps.media_type"
            "  AND a.owner_id=ps.media_id AND a.kind IN ('poster','still') AND a.local_path<>''"
            "  LIMIT 1) AS poster_path"
            " FROM playback_state ps WHERE ps.profile_id=?"
            " AND ps.media_type IN ('movie','episode')"
            " AND (ps.duration_seconds <= 0 OR ps.position_seconds / ps.duration_seconds < 0.95)"
            " AND ps.position_seconds > 5"
            " ORDER BY ps.updated_at DESC LIMIT ?",
            (profile_id, limit),
        )
        return [dict(r) for r in rows if r["title"]]

    # -- watched -----------------------------------------------------------------------
    def is_watched(self, profile_id: int, media_type: str, media_id: int) -> bool:
        return bool(
            self.db.scalar(
                "SELECT 1 FROM playback_history WHERE profile_id=? AND media_type=?"
                " AND media_id=? AND completed=1",
                (profile_id, media_type, media_id),
            )
        )

    def mark_watched(self, profile_id: int, media_type: str, media_id: int) -> None:
        """Record a completed session (idempotent)."""
        if self.is_watched(profile_id, media_type, media_id):
            return
        media_file_id = self.db.scalar(
            "SELECT l.media_file_id FROM media_file_links l"
            " WHERE l.media_item_type=? AND l.media_item_id=? ORDER BY l.is_primary DESC LIMIT 1",
            (media_type, media_id),
        )
        runtime = 0.0
        if media_type == "movie":
            runtime = float(self.db.scalar("SELECT runtime_seconds FROM movies WHERE id=?", (media_id,)) or 0)
        elif media_type == "episode":
            runtime = float(self.db.scalar("SELECT runtime_seconds FROM episodes WHERE id=?", (media_id,)) or 0)
        elif media_type == "track":
            runtime = float(self.db.scalar("SELECT duration_seconds FROM music_tracks WHERE id=?", (media_id,)) or 0)
        self.db.execute(
            "INSERT INTO playback_history (profile_id, media_file_id, media_type, media_id,"
            " finished_at, completed, duration_seconds)"
            " VALUES (?,?,?,?,datetime('now'),1,?)",
            (profile_id, media_file_id, media_type, media_id, runtime),
        )
        self.clear_position(profile_id, media_type, media_id)

    def mark_unwatched(self, profile_id: int, media_type: str, media_id: int) -> None:
        """Remove completed sessions and resume position for an item."""
        self.db.execute(
            "DELETE FROM playback_history WHERE profile_id=? AND media_type=? AND media_id=? AND completed=1",
            (profile_id, media_type, media_id),
        )
        self.clear_position(profile_id, media_type, media_id)

    def watched_episode_ids(self, profile_id: int, tv_show_id: int) -> set[int]:
        rows = self.db.query(
            "SELECT h.media_id FROM playback_history h JOIN episodes e ON e.id=h.media_id"
            " WHERE h.profile_id=? AND h.media_type='episode' AND e.tv_show_id=? AND h.completed=1",
            (profile_id, tv_show_id),
        )
        return {r["media_id"] for r in rows}

    # -- statistics -----------------------------------------------------------------------
    def total_watch_seconds(self, profile_id: int, media_type: str | None = None) -> float:
        where = "profile_id=?"
        params: list = [profile_id]
        if media_type:
            where += " AND media_type=?"
            params.append(media_type)
        value = self.db.scalar(
            f"SELECT SUM(position_seconds) FROM playback_history WHERE {where}", params
        )
        return float(value or 0.0)

    def watched_counts(self, profile_id: int) -> dict[str, int]:
        rows = self.db.query(
            "SELECT media_type, COUNT(*) n FROM"
            " (SELECT DISTINCT media_type, media_id FROM playback_history"
            "  WHERE profile_id=? AND completed=1) GROUP BY media_type",
            (profile_id,),
        )
        return {r["media_type"]: r["n"] for r in rows}
