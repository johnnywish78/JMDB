"""Search engine: FTS lookup + filters → grouped display results."""
from __future__ import annotations

import logging

from app.database.repositories import Repositories
from app.search.filters import SearchFilter
from app.search.index import SearchIndex

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, repos: Repositories, index: SearchIndex) -> None:
        self.repos = repos
        self.index = index

    # -- main entry ---------------------------------------------------------
    def search(self, query: str, filters: SearchFilter | None = None, profile_id: int = 1, limit_per_type: int = 30) -> dict[str, list[dict]]:
        filters = filters or SearchFilter()
        results: dict[str, list[dict]] = {}
        matched = self.index.lookup(query, types=filters.types, limit=limit_per_type * 4)
        if not matched and query.strip():
            matched = self._like_lookup(query, filters.types, limit_per_type)
        for entity_type in filters.types:
            ids = [eid for etype, eid in matched if etype == entity_type][:limit_per_type]
            if not ids:
                continue
            rows = self._display_rows(entity_type, ids, filters, profile_id)
            if rows:
                results[entity_type] = rows
        return results

    # -- helpers ----------------------------------------------------------------
    def _like_lookup(self, query: str, types: set[str], limit: int) -> list[tuple[str, int]]:
        """Fallback when FTS is disabled or returns nothing (e.g. phrase miss)."""
        like = f"%{query.strip()}%"
        out: list[tuple[str, int]] = []
        if "movie" in types:
            out += [("movie", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM movies WHERE title LIKE ? OR original_title LIKE ? LIMIT ?",
                (like, like, limit))]
        if "tv_show" in types:
            out += [("tv_show", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM tv_shows WHERE title LIKE ? OR original_title LIKE ? LIMIT ?",
                (like, like, limit))]
        if "episode" in types:
            out += [("episode", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM episodes WHERE title LIKE ? LIMIT ?", (like, limit))]
        if "person" in types:
            out += [("person", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM people WHERE name LIKE ? LIMIT ?", (like, limit))]
        if "artist" in types:
            out += [("artist", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM music_artists WHERE name LIKE ? LIMIT ?", (like, limit))]
        if "album" in types:
            out += [("album", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM music_albums WHERE title LIKE ? LIMIT ?", (like, limit))]
        if "track" in types:
            out += [("track", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM music_tracks WHERE title LIKE ? LIMIT ?", (like, limit))]
        if "collection" in types:
            out += [("collection", r["id"]) for r in self.repos.db.query(
                "SELECT id FROM user_collections WHERE name LIKE ? LIMIT ?", (like, limit))]
        return out

    def _display_rows(self, entity_type: str, ids: list[int], filters: SearchFilter, profile_id: int) -> list[dict]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        if entity_type == "movie":
            rows = self.repos.db.query(
                f"""SELECT m.id, m.title, m.year, m.rating, m.overview,
                (SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id
                 AND a.kind='poster' AND a.local_path<>'' LIMIT 1) AS poster_path
                FROM movies m WHERE m.id IN ({placeholders})""",
                ids,
            )
        elif entity_type == "tv_show":
            rows = self.repos.db.query(
                f"""SELECT s.id, s.title, s.first_air_date, s.rating, s.overview,
                substr(s.first_air_date,1,4) AS year,
                (SELECT a.local_path FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id
                 AND a.kind='poster' AND a.local_path<>'' LIMIT 1) AS poster_path
                FROM tv_shows s WHERE s.id IN ({placeholders})""",
                ids,
            )
        elif entity_type == "episode":
            rows = self.repos.db.query(
                f"""SELECT e.id, e.title, e.season_number, e.episode_number, e.overview,
                (SELECT s.title FROM tv_shows s WHERE s.id=e.tv_show_id) AS show_title,
                (SELECT a.local_path FROM artwork a WHERE a.owner_type='episode' AND a.owner_id=e.id
                 AND a.kind='still' AND a.local_path<>'' LIMIT 1) AS poster_path
                FROM episodes e WHERE e.id IN ({placeholders})""",
                ids,
            )
        elif entity_type == "person":
            rows = self.repos.db.query(
                f"""SELECT p.id, p.name AS title,
                (SELECT a.local_path FROM artwork a WHERE a.owner_type='person' AND a.owner_id=p.id
                 AND a.kind='profile' AND a.local_path<>'' LIMIT 1) AS poster_path
                FROM people p WHERE p.id IN ({placeholders})""",
                ids,
            )
        elif entity_type == "artist":
            rows = self.repos.db.query(
                f"""SELECT a.id, a.name AS title,
                (SELECT aw.local_path FROM artwork aw WHERE aw.owner_type='artist' AND aw.owner_id=a.id
                 AND aw.local_path<>'' LIMIT 1) AS poster_path
                FROM music_artists a WHERE a.id IN ({placeholders})""",
                ids,
            )
        elif entity_type == "album":
            rows = self.repos.db.query(
                f"""SELECT al.id, al.title, al.year,
                (SELECT ar.name FROM music_artists ar WHERE ar.id=al.artist_id) AS show_title,
                (SELECT a.local_path FROM artwork a WHERE a.owner_type='album' AND a.owner_id=al.id
                 AND a.kind='album_cover' AND a.local_path<>'' LIMIT 1) AS poster_path
                FROM music_albums al WHERE al.id IN ({placeholders})""",
                ids,
            )
        elif entity_type == "track":
            rows = self.repos.db.query(
                f"""SELECT t.id, t.title, t.duration_seconds,
                (SELECT ar.name FROM music_artists ar WHERE ar.id=t.artist_id) AS show_title,
                (SELECT a.local_path FROM artwork a WHERE a.owner_type='album' AND a.owner_id=t.album_id
                 AND a.kind='album_cover' AND a.local_path<>'' LIMIT 1) AS poster_path
                FROM music_tracks t WHERE t.id IN ({placeholders})""",
                ids,
            )
        elif entity_type == "collection":
            rows = self.repos.db.query(
                f"SELECT id, name AS title, description AS overview FROM user_collections WHERE id IN ({placeholders})",
                ids,
            )
        else:
            rows = []

        out = []
        for row in rows:
            data = dict(row)
            data["entity_type"] = entity_type
            if not self._passes_filters(entity_type, data, filters, profile_id):
                continue
            out.append(data)
        return out

    def _passes_filters(self, entity_type: str, row: dict, filters: SearchFilter, profile_id: int) -> bool:
        if filters.genre and entity_type in ("movie", "tv_show"):
            if filters.genre not in self.repos.taxonomy.genres_for(entity_type, row["id"]):
                return False
        if filters.year_from is not None or filters.year_to is not None:
            year = row.get("year")
            if not isinstance(year, int):
                year = int(str(year)[:4]) if str(year)[:4].isdigit() else None
            if year is None:
                return False
            if filters.year_from is not None and year < filters.year_from:
                return False
            if filters.year_to is not None and year > filters.year_to:
                return False
        if filters.min_rating is not None and entity_type in ("movie", "tv_show"):
            rating = row.get("rating") or 0
            if rating < filters.min_rating:
                return False
        if filters.favorites_only:
            if not self.repos.lists.is_favorite(profile_id, entity_type, row["id"]):
                return False
        if filters.watchlist_only:
            if not self.repos.lists.in_watchlist(profile_id, entity_type, row["id"]):
                return False
        if filters.unwatched_only or filters.watched_only:
            if entity_type not in ("movie", "episode"):
                return False
            watched = self.repos.playback.is_watched(profile_id, entity_type, row["id"])
            if filters.unwatched_only and watched:
                return False
            if filters.watched_only and not watched:
                return False
        return True

    # -- browse helpers -------------------------------------------------------------
    def all_genres(self) -> list[str]:
        return [g.name for g in self.repos.taxonomy.all_genres()]

    def suggest(self, prefix: str, limit: int = 8) -> list[dict]:
        """Quick title suggestions for the search bar dropdown."""
        results = self.search(prefix, SearchFilter(types={"movie", "tv_show", "artist", "album"}), limit_per_type=4)
        out = []
        for entity_type, rows in results.items():
            for row in rows:
                out.append({
                    "entity_type": entity_type,
                    "id": row["id"],
                    "title": row.get("title", ""),
                    "year": row.get("year"),
                })
        return out[:limit]
