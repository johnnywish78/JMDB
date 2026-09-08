"""Repositories — the only SQL-facing layer above Database. UI never writes SQL."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.database.connection import Database
from app.domain.enums import MediaKind, PersonRole


def _now() -> int:
    return int(time.time() * 1000)


class MediaRepository:
    _COLUMNS = {
        "original_title", "rating", "overview", "runtime_min", "genres", "file_path",
        "poster_path", "backdrop_path", "imdb_id", "tmdb_id", "seasons",
    }
    _DEFAULTS = {
        "original_title": "", "rating": 0.0, "overview": "", "runtime_min": 0,
        "genres": "[]", "file_path": None, "poster_path": None, "backdrop_path": None,
        "imdb_id": "", "tmdb_id": None, "seasons": "[]",
    }

    def __init__(self, db: Database):
        self.db = db

    def upsert(self, kind: str, title: str, year: int | None = None, **fields: Any) -> int:
        row = self.db.query_one(
            "SELECT id FROM media WHERE kind=? AND title=? AND year IS ?",
            (kind, title, year),
        )
        # only keys passed by the caller are written — updates never wipe metadata
        passed: dict[str, Any] = {}
        for key, value in fields.items():
            if key in self._COLUMNS:
                passed[key] = (json.dumps(value, ensure_ascii=False)
                               if key in ("genres", "seasons") else value)
        if row:
            if passed:
                sets = ", ".join(f"{k}=?" for k in passed)
                self.db.execute(f"UPDATE media SET {sets} WHERE id=?", (*passed.values(), row["id"]))
            return int(row["id"])
        cols = {**self._DEFAULTS, **passed}
        names = ", ".join(["kind", "title", "year", *cols.keys()])
        marks = ", ".join("?" for _ in cols)
        return self.db.execute(
            f"INSERT INTO media ({names}) VALUES (?, ?, ?, {marks})",
            (kind, title, year, *cols.values()),
        )

    def get(self, media_id: int) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM media WHERE id=?", (media_id,))
        return self._expand(row) if row else None

    def apply_metadata(self, media_id: int, meta: dict[str, Any]) -> None:
        """Apply metadata with field precedence: only write non-empty values,
        preserving existing high-quality fields when the provider returns empty."""
        mapping = {
            "original_title": "original_title",
            "rating": "rating",
            "overview": "overview",
            "runtime_min": "runtime_min",
            "poster_path": "poster_path",
            "backdrop_path": "backdrop_path",
            "imdb_id": "imdb_id",
            "tmdb_id": "tmdb_id",
            # Provider URLs are resolved by ArtworkStore into local paths on read;
            # store the URL as poster/backdrop_path here for resolution later.
            "poster_url": "poster_path",
            "backdrop_url": "backdrop_path",
        }
        sets, params = [], []
        existing = self.get(media_id) or {}
        for key, col in mapping.items():
            val = meta.get(key)
            if val is None:
                continue
            current = existing.get(col)
            # For numeric fields, only overwrite if new value is meaningfully positive
            if col in ("rating", "runtime_min"):
                if val > 0 and val != current:
                    sets.append(f"{col}=?"); params.append(val)
            # For URL/path fields, only overwrite if new value is a URL (fresh download)
            # or current is empty/None
            elif col in ("poster_path", "backdrop_path"):
                if val and (not current or str(val).startswith("http")):
                    sets.append(f"{col}=?"); params.append(val)
            # For text fields, only overwrite if new value is non-empty and different
            elif isinstance(val, str) and val and val != current or col == "tmdb_id" and val is not None and val != current:
                sets.append(f"{col}=?"); params.append(val)
        if meta.get("genres"):
            current_genres = set(json.loads(existing.get("genres") or "[]") if isinstance(existing.get("genres"), str) else existing.get("genres") or [])
            new_genres = set(meta["genres"])
            if new_genres - current_genres:
                sets.append("genres=?")
                params.append(json.dumps(meta["genres"], ensure_ascii=False))
        if meta.get("year") and meta["year"] != existing.get("year"):
            sets.append("year=?"); params.append(meta["year"])
        if sets:
            self.db.execute(f"UPDATE media SET {', '.join(sets)} WHERE id=?", (*params, media_id))

    def list(self, kind: str, sort: str = "rating", genre: str | None = None,
             limit: int | None = None) -> list[dict[str, Any]]:
        orders = {
            "rating": "rating DESC, title", "title": "title COLLATE NOCASE",
            "newest": "year DESC NULLS LAST, title", "added": "added_at DESC",
            "runtime": "runtime_min DESC",
        }
        sql = "SELECT * FROM media WHERE kind=?"
        params: list[Any] = [kind]
        if genre:
            sql += " AND genres LIKE ?"; params.append(f'%"{genre}"%')
        sql += f" ORDER BY {orders.get(sort, orders['rating'])}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [self._expand(r) for r in self.db.query(sql, params)]

    def by_ids(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        marks = ",".join("?" for _ in ids)
        return [self._expand(r) for r in self.db.query(f"SELECT * FROM media WHERE id IN ({marks})", ids)]

    def distinct_genres(self, kind: str) -> list[str]:
        found: set[str] = set()
        for row in self.db.query("SELECT genres FROM media WHERE kind=?", (kind,)):
            found.update(json.loads(row["genres"] or "[]"))
        return sorted(found)

    def count(self, kind: str) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS n FROM media WHERE kind=?", (kind,))
        return int(row["n"]) if row else 0

    def delete_file_missing(self) -> int:
        """Remove rows whose file_path no longer exists. Returns count."""
        rows = self.db.query("SELECT id, file_path FROM media WHERE file_path IS NOT NULL")
        gone = [r["id"] for r in rows if r["file_path"] and not Path(r["file_path"]).exists()]
        for mid in gone:
            self.db.execute("DELETE FROM media WHERE id=?", (mid,))
        return len(gone)

    @staticmethod
    def _expand(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out["genres"] = json.loads(out.get("genres") or "[]")
        out["seasons"] = json.loads(out.get("seasons") or "[]")
        return out


class EpisodeRepository:
    def __init__(self, db: Database):
        self.db = db

    def upsert(self, show_id: int, season: int, number: int, **fields: Any) -> int:
        self.db.execute(
            """INSERT INTO episodes (show_id, season, number, title, runtime_min, file_path)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(show_id, season, number) DO UPDATE SET
                 title=excluded.title, runtime_min=excluded.runtime_min, file_path=excluded.file_path""",
            (show_id, season, number, fields.get("title", ""),
             fields.get("runtime_min", 0), fields.get("file_path")),
        )
        row = self.db.query_one(
            "SELECT id FROM episodes WHERE show_id=? AND season=? AND number=?",
            (show_id, season, number))
        return int(row["id"])

    def for_show(self, show_id: int, season: int | None = None) -> list[dict[str, Any]]:
        if season is None:
            return self.db.query(
                "SELECT * FROM episodes WHERE show_id=? ORDER BY season, number", (show_id,))
        return self.db.query(
            "SELECT * FROM episodes WHERE show_id=? AND season=? ORDER BY number", (show_id, season))

    def get(self, episode_id: int) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM episodes WHERE id=?", (episode_id,))
        return dict(row) if row else None

    def mark_watched(self, episode_id: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO episodes_watched (episode_id, watched_at) VALUES (?, ?)",
            (episode_id, _now()))

    def mark_unwatched(self, episode_id: int) -> None:
        self.db.execute("DELETE FROM episodes_watched WHERE episode_id=?", (episode_id,))

    def watched_ids(self, show_id: int) -> set[int]:
        rows = self.db.query(
            """SELECT ew.episode_id FROM episodes_watched ew
               JOIN episodes e ON e.id=ew.episode_id WHERE e.show_id=?""", (show_id,))
        return {int(r["episode_id"]) for r in rows}

    def progress_of_show(self, show_id: int) -> tuple[int, int]:
        eps = self.for_show(show_id)
        watched = self.watched_ids(show_id)
        done = sum(1 for e in eps if e["id"] in watched)
        return done, len(eps)

    def next_unwatched(self, show_id: int) -> dict[str, Any] | None:
        watched = self.watched_ids(show_id)
        for ep in self.for_show(show_id):
            if ep["id"] not in watched:
                return ep
        return None

    def next_after(self, episode_id: int) -> dict[str, Any] | None:
        ep = self.get(episode_id)
        if not ep:
            return None
        row = self.db.query_one(
            """SELECT * FROM episodes WHERE show_id=?
               AND (season > ? OR (season = ? AND number > ?))
               ORDER BY season, number LIMIT 1""",
            (ep["show_id"], ep["season"], ep["season"], ep["number"]))
        return dict(row) if row else None


class PeopleRepository:
    def __init__(self, db: Database):
        self.db = db

    def link(self, media_id: int, name: str, role: str = PersonRole.ACTOR) -> None:
        name = name.strip()
        if not name:
            return
        pid = self.db.execute("INSERT OR IGNORE INTO people (name) VALUES (?)", (name,))
        if not pid:
            row = self.db.query_one("SELECT id FROM people WHERE name=?", (name,))
            pid = int(row["id"])
        role = role.value if isinstance(role, PersonRole) else str(role)
        self.db.execute(
            "INSERT OR IGNORE INTO media_people (media_id, person_id, role) VALUES (?, ?, ?)",
            (media_id, pid, role))

    def for_media(self, media_id: int) -> list[dict[str, Any]]:
        return self.db.query(
            """SELECT p.name, mp.role FROM media_people mp
               JOIN people p ON p.id=mp.person_id WHERE mp.media_id=?
               ORDER BY CASE mp.role WHEN 'director' THEN 0 WHEN 'creator' THEN 1 ELSE 2 END, p.name""",
            (media_id,))

    def all_people(self) -> list[dict[str, Any]]:
        return self.db.query(
            """SELECT p.name, COUNT(DISTINCT mp.media_id) AS n,
                      GROUP_CONCAT(DISTINCT mp.role) AS roles
               FROM people p JOIN media_people mp ON mp.person_id=p.id
               GROUP BY p.id ORDER BY n DESC, p.name""")

    def items_for(self, name: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            """SELECT m.*, mp.role FROM media m
               JOIN media_people mp ON mp.media_id=m.id
               JOIN people p ON p.id=mp.person_id WHERE p.name=? ORDER BY m.rating DESC""", (name,))
        return [MediaRepository._expand(dict(r)) for r in rows]


class LibraryStateRepository:
    """Favorites / watchlist / watched / personal ratings."""
    def __init__(self, db: Database):
        self.db = db

    def _ids(self, table: str) -> set[int]:
        return {int(r["media_id"]) for r in self.db.query(f"SELECT media_id FROM {table}")}

    def _toggle(self, table: str, media_id: int) -> bool:
        if self.db.query_one(f"SELECT media_id FROM {table} WHERE media_id=?", (media_id,)):
            self.db.execute(f"DELETE FROM {table} WHERE media_id=?", (media_id,))
            return False
        self.db.execute(f"INSERT INTO {table} (media_id, added_at) VALUES (?, ?)", (media_id, _now()))
        return True

    def toggle_favorite(self, media_id: int) -> bool:  return self._toggle("favorites", media_id)
    def toggle_watchlist(self, media_id: int) -> bool: return self._toggle("watchlist", media_id)
    def favorites(self) -> set[int]:   return self._ids("favorites")
    def watchlist(self) -> set[int]:   return self._ids("watchlist")
    def watched_movies(self) -> set[int]: return self._ids("movies_watched")

    def mark_movie_watched(self, media_id: int, watched: bool = True) -> None:
        if watched:
            self.db.execute(
                "INSERT OR REPLACE INTO movies_watched (media_id, watched_at) VALUES (?, ?)", (media_id, _now()))
        else:
            self.db.execute("DELETE FROM movies_watched WHERE media_id=?", (media_id,))

    def set_rating(self, media_id: int, value: int | None) -> None:
        if value is None or value <= 0:
            self.db.execute("DELETE FROM ratings WHERE media_id=?", (media_id,))
        else:
            self.db.execute(
                "INSERT OR REPLACE INTO ratings (media_id, value, updated_at) VALUES (?, ?, ?)",
                (media_id, min(10, int(value)), _now()))

    def ratings_map(self) -> dict[int, int]:
        return {int(r["media_id"]): int(r["value"]) for r in self.db.query("SELECT media_id, value FROM ratings")}


class ProgressRepository:
    def __init__(self, db: Database):
        self.db = db

    def set_position(self, media_key: str, position_s: int, duration_s: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO playback_progress (media_key, position_s, duration_s, updated_at) VALUES (?, ?, ?, ?)",
            (media_key, int(position_s), int(duration_s), _now()))

    def get(self, media_key: str) -> dict[str, Any] | None:
        return self.db.query_one("SELECT * FROM playback_progress WHERE media_key=?", (media_key,))

    def clear(self, media_key: str) -> None:
        self.db.execute("DELETE FROM playback_progress WHERE media_key=?", (media_key,))

    def in_progress(self, min_seconds: int = 30) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM playback_progress WHERE position_s>=? ORDER BY updated_at DESC LIMIT 20",
            (min_seconds,))


class HistoryRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, media_key: str, media_title: str, subtitle: str,
            started_at: int, finished_at: int) -> int:
        return self.db.execute(
            "INSERT INTO watch_history (media_key, media_title, subtitle, started_at, finished_at) VALUES (?, ?, ?, ?, ?)",
            (media_key, media_title, subtitle, started_at, finished_at))

    def recent(self, limit: int = 300) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM watch_history ORDER BY finished_at DESC LIMIT ?", (limit,))

    def clear(self) -> None:
        self.db.execute("DELETE FROM watch_history")


class BookmarkRepository:
    def __init__(self, db: Database):
        self.db = db

    def all(self) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM bookmarks ORDER BY position, name")

    def add(self, name: str, url: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO bookmarks (name, url, position) VALUES (?, ?, COALESCE((SELECT MAX(position)+1 FROM bookmarks), 0))",
            (name, url))

    def remove(self, bookmark_id: int) -> None:
        self.db.execute("DELETE FROM bookmarks WHERE id=?", (bookmark_id,))


KINDS = {k.value for k in MediaKind}
