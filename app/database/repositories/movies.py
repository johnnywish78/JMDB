"""Movies repository, including franchise collections."""
from __future__ import annotations

from typing import Any, Optional

from app.domain.models import Movie, MovieCollection
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses

POSTER_SUB = (
    "(SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id"
    " AND a.kind='poster' AND a.local_path<>'' ORDER BY a.id LIMIT 1) AS poster_path"
)
BACKDROP_SUB = (
    "(SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id"
    " AND a.kind='backdrop' AND a.local_path<>'' ORDER BY a.id LIMIT 1) AS backdrop_path"
)
FILES_SUB = (
    "(SELECT COUNT(*) FROM media_file_links l JOIN media_files f ON f.id=l.media_file_id"
    " WHERE l.media_item_type='movie' AND l.media_item_id=m.id AND f.is_missing=0) AS file_count"
)


class MoviesRepository(BaseRepository):
    # -- CRUD --------------------------------------------------------------
    def get(self, movie_id: int) -> Movie | None:
        row = self.db.query_one("SELECT * FROM movies WHERE id=?", (movie_id,))
        return row_to_dataclass(row, Movie) if row else None

    def find_by_title_year(self, title: str, year: int | None) -> Movie | None:
        if year is not None:
            row = self.db.query_one(
                "SELECT * FROM movies WHERE (lower(title)=lower(?) OR lower(original_title)=lower(?))"
                " AND year=?",
                (title, title, year),
            )
            if row:
                return row_to_dataclass(row, Movie)
        row = self.db.query_one(
            "SELECT * FROM movies WHERE (lower(title)=lower(?) OR lower(original_title)=lower(?))"
            " ORDER BY (year IS NULL) LIMIT 1",
            (title, title),
        )
        return row_to_dataclass(row, Movie) if row else None

    def create(self, movie: Movie) -> int:
        cur = self.db.execute(
            "INSERT INTO movies (title, original_title, sort_title, year, release_date,"
            " runtime_seconds, overview, tagline, rating, vote_count, certification,"
            " languages, countries, collection_id)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                movie.title, movie.original_title, movie.sort_title, movie.year,
                movie.release_date, movie.runtime_seconds, movie.overview, movie.tagline,
                movie.rating, movie.vote_count, movie.certification, movie.languages,
                movie.countries, movie.collection_id,
            ),
        )
        return int(cur.lastrowid)

    def update(self, movie_id: int, values: dict[str, Any]) -> None:
        if not values:
            return
        allowed = {
            "title", "original_title", "sort_title", "year", "release_date",
            "runtime_seconds", "overview", "tagline", "rating", "vote_count",
            "certification", "languages", "countries", "collection_id",
        }
        sets, params = [], []
        for key, value in values.items():
            if key in allowed:
                sets.append(f"{key}=?")
                params.append(value)
        if not sets:
            return
        params.append(movie_id)
        self.db.execute(
            f"UPDATE movies SET {', '.join(sets)}, updated_at=datetime('now') WHERE id=?",
            params,
        )

    def delete(self, movie_id: int) -> None:
        self.db.execute("DELETE FROM movies WHERE id=?", (movie_id,))

    def count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM movies") or 0)

    # -- listing ------------------------------------------------------------
    def list_page(
        self,
        profile_id: int,
        page: int = 0,
        per_page: int = 60,
        genre: str = "",
        year_from: int | None = None,
        year_to: int | None = None,
        min_rating: float | None = None,
        query: str = "",
        sort: str = "title",
        favorites_only: bool = False,
        watchlist_only: bool = False,
        unwatched_only: bool = False,
        watched_only: bool = False,
        collection_id: int | None = None,
    ) -> tuple[list[dict], int]:
        where, params = ["1=1"], []
        if genre:
            where.append(
                "m.id IN (SELECT mg.media_id FROM media_genres mg JOIN genres g ON g.id=mg.genre_id"
                " WHERE mg.media_type='movie' AND g.name=?)"
            )
            params.append(genre)
        if year_from is not None:
            where.append("COALESCE(m.year, 0) >= ?")
            params.append(year_from)
        if year_to is not None:
            where.append("COALESCE(m.year, 9999) <= ?")
            params.append(year_to)
        if min_rating is not None:
            where.append("COALESCE(m.rating, 0) >= ?")
            params.append(min_rating)
        if query:
            where.append("(m.title LIKE ? OR m.original_title LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if favorites_only:
            where.append("EXISTS (SELECT 1 FROM favorites f WHERE f.profile_id=? AND f.media_type='movie' AND f.media_id=m.id)")
            params.append(profile_id)
        if watchlist_only:
            where.append("EXISTS (SELECT 1 FROM watchlist w WHERE w.profile_id=? AND w.media_type='movie' AND w.media_id=m.id)")
            params.append(profile_id)
        watched_exists = (
            "EXISTS (SELECT 1 FROM playback_history h WHERE h.profile_id=? AND h.media_type='movie'"
            " AND h.media_id=m.id AND h.completed=1)"
        )
        if unwatched_only:
            where.append(f"NOT {watched_exists}")
            params.append(profile_id)
        if watched_only:
            where.append(watched_exists)
            params.append(profile_id)
        if collection_id is not None:
            where.append(
                "m.id IN (SELECT ci.media_id FROM collection_items ci"
                " WHERE ci.collection_id=? AND ci.media_type='movie')"
            )
            params.append(collection_id)

        order = {
            "title": "m.sort_title COLLATE NOCASE, m.title COLLATE NOCASE",
            "year": "m.year DESC",
            "added": "m.added_at DESC",
            "rating": "m.rating DESC",
        }.get(sort, "m.sort_title COLLATE NOCASE")

        base_where = " AND ".join(where)
        total = int(
            self.db.scalar(f"SELECT COUNT(*) FROM movies m WHERE {base_where}", params) or 0
        )
        rows = self.db.query(
            f"SELECT m.id, m.title, m.year, m.rating, m.certification, m.runtime_seconds,"
            f" m.overview, {POSTER_SUB}, {FILES_SUB},"
            " EXISTS (SELECT 1 FROM favorites f WHERE f.profile_id=? AND f.media_type='movie' AND f.media_id=m.id) AS is_favorite,"
            " EXISTS (SELECT 1 FROM watchlist w WHERE w.profile_id=? AND w.media_type='movie' AND w.media_id=m.id) AS in_watchlist,"
            f" {watched_exists} AS watched"
            f" FROM movies m WHERE {base_where}"
            f" ORDER BY {order} LIMIT ? OFFSET ?",
            [profile_id, profile_id, profile_id, *params, per_page, page * per_page],
        )
        return [dict(r) for r in rows], total

    def recently_added(self, profile_id: int, limit: int = 20) -> list[dict]:
        rows = self.db.query(
            f"SELECT m.id, m.title, m.year, m.rating, {POSTER_SUB}, m.added_at,"
            f" {FILES_SUB} FROM movies m ORDER BY m.added_at DESC, m.id DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    def ids_needing_metadata(self, limit: int = 50) -> list[int]:
        rows = self.db.query(
            "SELECT m.id FROM movies m WHERE m.overview='' ORDER BY m.added_at LIMIT ?",
            (limit,),
        )
        return [r["id"] for r in rows]

    # -- franchises -----------------------------------------------------------
    def get_or_create_collection(self, name: str, overview: str = "") -> MovieCollection:
        name = name.strip()
        if not name:
            raise ValueError("collection name required")
        row = self.db.query_one("SELECT * FROM movie_collections WHERE name=?", (name,))
        if row is None:
            cur = self.db.execute(
                "INSERT INTO movie_collections (name, overview) VALUES (?,?)", (name, overview)
            )
            row = self.db.query_one("SELECT * FROM movie_collections WHERE id=?", (cur.lastrowid,))
        return row_to_dataclass(row, MovieCollection)

    def list_franchises(self) -> list[MovieCollection]:
        return rows_to_dataclasses(
            self.db.query(
                "SELECT mc.*, (SELECT COUNT(*) FROM movies m WHERE m.collection_id=mc.id) AS movie_count"
                " FROM movie_collections mc HAVING movie_count > 0 ORDER BY mc.name"
            ),
            MovieCollection,
        )

    def movies_in_collection(self, collection_id: int, profile_id: int) -> list[dict]:
        rows = self.db.query(
            f"SELECT m.id, m.title, m.year, m.rating, {POSTER_SUB}, 0 AS file_count"
            " FROM movies m WHERE m.collection_id=? ORDER BY m.year",
            (collection_id,),
        )
        return [dict(r) for r in rows]
