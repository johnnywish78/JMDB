"""FTS5 search index over the library.

The index is a derived structure: the tables are the source of truth, the
index is rebuilt incrementally as entities change and fully on demand.
Falls back to LIKE queries when FTS5 is unavailable.
"""
from __future__ import annotations

import logging

from app.database.connection import Database

logger = logging.getLogger(__name__)

FTS_TABLE = "search_index"


class SearchIndex:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._fts_enabled = False
        try:
            self.db.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5("
                " content, entity_type UNINDEXED, entity_id UNINDEXED,"
                " tokenize='porter unicode61')"
            )
            self._fts_enabled = True
        except Exception as exc:
            logger.warning("FTS5 unavailable (%s); search falls back to LIKE", exc)
            self._fts_enabled = False

    @property
    def enabled(self) -> bool:
        return self._fts_enabled

    _CONTENT_COLUMNS = ("title", "original_title", "overview", "year", "genres", "people", "tags")

    @classmethod
    def _row_content(cls, row) -> str:
        parts = []
        for column in cls._CONTENT_COLUMNS:
            try:
                value = row[column]
            except (IndexError, KeyError):
                value = None
            if value:
                parts.append(str(value))
        return " ".join(parts)

    # -- public --------------------------------------------------------------
    def rebuild(self) -> int:
        if not self._fts_enabled:
            return 0
        with self.db.transaction() as conn:
            conn.execute(f"DELETE FROM {FTS_TABLE}")
            total = 0
            for sql, params in self._all_entities():
                for row in conn.execute(sql, params).fetchall():
                    content = self._row_content(row)
                    if content.strip():
                        conn.execute(
                            f"INSERT INTO {FTS_TABLE} (content, entity_type, entity_id)"
                            " VALUES (?,?,?)",
                            (content, row["entity_type"], row["entity_id"]),
                        )
                        total += 1
        return total

    def update(self, entity_type: str, entity_id: int) -> None:
        """Refresh one entity in the index (call after metadata/scan changes)."""
        if not self._fts_enabled:
            return
        sql, params = self._entity_sql(entity_type, entity_id)
        if sql is None:
            return
        with self.db.transaction() as conn:
            conn.execute(
                f"DELETE FROM {FTS_TABLE} WHERE entity_type=? AND entity_id=?",
                (entity_type, entity_id),
            )
            for row in conn.execute(sql, params).fetchall():
                content = self._row_content(row)
                if content.strip():
                    conn.execute(
                        f"INSERT INTO {FTS_TABLE} (content, entity_type, entity_id) VALUES (?,?,?)",
                        (content, row["entity_type"], row["entity_id"]),
                    )

    def remove(self, entity_type: str, entity_id: int) -> None:
        if not self._fts_enabled:
            return
        self.db.execute(
            f"DELETE FROM {FTS_TABLE} WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        )

    def lookup(self, query: str, types: set[str] | None = None, limit: int = 200) -> list[tuple[str, int]]:
        """FTS lookup with prefix support; returns (entity_type, entity_id)."""
        if not self._fts_enabled or not query.strip():
            return []
        terms = [t for t in query.strip().split() if t]
        if not terms:
            return []
        match = " ".join(f'"{t}"*' for t in terms)  # prefix search per term
        sql = (
            f"SELECT entity_type, entity_id FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH ?"
        )
        params: list = [match]
        if types:
            placeholders = ",".join("?" * len(types))
            sql += f" AND entity_type IN ({placeholders})"
            params.extend(types)
        sql += " LIMIT ?"
        params.append(limit)
        return [(r["entity_type"], r["entity_id"]) for r in self.db.query(sql, params)]

    # -- entity SQL ------------------------------------------------------------
    def _all_entities(self):
        yield (
            """SELECT 'movie' AS entity_type, m.id AS entity_id, m.title, m.original_title,
               m.overview, m.year,
               (SELECT group_concat(g.name, ' ') FROM media_genres mg JOIN genres g ON g.id=mg.genre_id
                WHERE mg.media_type='movie' AND mg.media_id=m.id) AS genres,
               (SELECT group_concat(p.name, ' ') FROM credits c JOIN people p ON p.id=c.person_id
                WHERE c.media_type='movie' AND c.media_id=m.id) AS people,
               (SELECT group_concat(t.name, ' ') FROM media_tags mt JOIN tags t ON t.id=mt.tag_id
                WHERE mt.media_type='movie' AND mt.media_id=m.id) AS tags
               FROM movies m""",
            (),
        )
        yield (
            """SELECT 'tv_show' AS entity_type, s.id AS entity_id, s.title, s.original_title,
               s.overview, NULL as year,
               (SELECT group_concat(g.name, ' ') FROM media_genres mg JOIN genres g ON g.id=mg.genre_id
                WHERE mg.media_type='tv_show' AND mg.media_id=s.id) AS genres,
               (SELECT group_concat(p.name, ' ') FROM credits c JOIN people p ON p.id=c.person_id
                WHERE c.media_type='tv_show' AND c.media_id=s.id) AS people,
               '' AS tags
               FROM tv_shows s""",
            (),
        )
        yield (
            """SELECT 'episode' AS entity_type, e.id AS entity_id,
               (SELECT s.title FROM tv_shows s WHERE s.id=e.tv_show_id) AS title,
               '' AS original_title, e.overview, NULL as year, '' AS genres, '' AS people, '' AS tags
               FROM episodes e""",
            (),
        )
        yield (
            """SELECT 'person' AS entity_type, p.id AS entity_id, p.name AS title,
               '' AS original_title, p.biography AS overview, NULL as year,
               '' AS genres, '' AS people, '' AS tags
               FROM people p""",
            (),
        )
        yield (
            """SELECT 'artist' AS entity_type, a.id AS entity_id, a.name AS title,
               '' AS original_title, a.biography AS overview, NULL as year,
               (SELECT group_concat(g.name, ' ') FROM artist_genres ag JOIN music_genres g ON g.id=ag.genre_id
                WHERE ag.artist_id=a.id) AS genres, '' AS people, '' AS tags
               FROM music_artists a""",
            (),
        )
        yield (
            """SELECT 'album' AS entity_type, al.id AS entity_id, al.title,
               '' AS original_title, '' AS overview, al.year,
               (SELECT group_concat(g.name, ' ') FROM album_genres ag JOIN music_genres g ON g.id=ag.genre_id
                WHERE ag.album_id=al.id) AS genres,
               (SELECT ar.name FROM music_artists ar WHERE ar.id=al.artist_id) AS people,
               '' AS tags
               FROM music_albums al""",
            (),
        )
        yield (
            """SELECT 'track' AS entity_type, t.id AS entity_id, t.title,
               '' AS original_title, '' AS overview, NULL as year, '' AS genres,
               (SELECT ar.name FROM music_artists ar WHERE ar.id=t.artist_id) AS people,
               '' AS tags
               FROM music_tracks t""",
            (),
        )
        yield (
            """SELECT 'collection' AS entity_type, uc.id AS entity_id, uc.name AS title,
               '' AS original_title, uc.description AS overview, NULL as year,
               '' AS genres, '' AS people, '' AS tags
               FROM user_collections uc""",
            (),
        )

    _ENTITY_KINDS = {"movie", "tv_show", "episode", "person", "artist", "album", "track", "collection"}

    def _entity_sql(self, entity_type: str, entity_id: int):
        if entity_type not in self._ENTITY_KINDS:
            return None, ()
        for sql, _ in self._all_entities():
            if f"'{entity_type}' AS entity_type" in sql:
                wrapped = f"SELECT * FROM ({sql}) WHERE entity_id = ?"
                return wrapped, (entity_id,)
        return None, ()
