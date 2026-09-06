"""User collections (playlists of library items) repository."""
from __future__ import annotations

from app.domain.models import UserCollection
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses


class CollectionsRepository(BaseRepository):
    def create(self, name: str, description: str = "") -> UserCollection:
        cur = self.db.execute(
            "INSERT INTO user_collections (name, description) VALUES (?,?)",
            (name.strip(), description),
        )
        return UserCollection(id=cur.lastrowid, name=name.strip(), description=description)

    def get(self, collection_id: int) -> UserCollection | None:
        row = self.db.query_one("SELECT * FROM user_collections WHERE id=?", (collection_id,))
        return row_to_dataclass(row, UserCollection) if row else None

    def get_by_name(self, name: str) -> UserCollection | None:
        row = self.db.query_one(
            "SELECT * FROM user_collections WHERE lower(name)=lower(?)", (name,)
        )
        return row_to_dataclass(row, UserCollection) if row else None

    def list(self) -> list[dict]:
        rows = self.db.query(
            "SELECT uc.id, uc.name, uc.description, uc.created_at,"
            " (SELECT COUNT(*) FROM collection_items ci WHERE ci.collection_id=uc.id) AS item_count"
            " FROM user_collections uc ORDER BY uc.name COLLATE NOCASE"
        )
        return [dict(r) for r in rows]

    def rename(self, collection_id: int, name: str, description: str | None = None) -> None:
        if description is None:
            self.db.execute(
                "UPDATE user_collections SET name=? WHERE id=?", (name.strip(), collection_id)
            )
        else:
            self.db.execute(
                "UPDATE user_collections SET name=?, description=? WHERE id=?",
                (name.strip(), description, collection_id),
            )

    def delete(self, collection_id: int) -> None:
        self.db.execute("DELETE FROM user_collections WHERE id=?", (collection_id,))

    # -- items ---------------------------------------------------------------
    def add_item(self, collection_id: int, media_type: str, media_id: int) -> None:
        position = int(
            self.db.scalar(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM collection_items WHERE collection_id=?",
                (collection_id,),
            )
            or 0
        )
        self.db.execute(
            "INSERT OR IGNORE INTO collection_items (collection_id, media_type, media_id, position)"
            " VALUES (?,?,?,?)",
            (collection_id, media_type, media_id, position),
        )

    def remove_item(self, collection_id: int, media_type: str, media_id: int) -> None:
        self.db.execute(
            "DELETE FROM collection_items WHERE collection_id=? AND media_type=? AND media_id=?",
            (collection_id, media_type, media_id),
        )

    def items(self, collection_id: int) -> list[dict]:
        """Items with joined display info, ordered by position."""
        rows = self.db.query(
            "SELECT ci.media_type, ci.media_id, ci.position,"
            " CASE ci.media_type"
            "  WHEN 'movie' THEN (SELECT m.title FROM movies m WHERE m.id=ci.media_id)"
            "  WHEN 'tv_show' THEN (SELECT s.title FROM tv_shows s WHERE s.id=ci.media_id)"
            "  WHEN 'artist' THEN (SELECT a.name FROM music_artists a WHERE a.id=ci.media_id)"
            "  WHEN 'album' THEN (SELECT al.title FROM music_albums al WHERE al.id=ci.media_id)"
            " END AS title,"
            " CASE ci.media_type"
            "  WHEN 'movie' THEN (SELECT m.year FROM movies m WHERE m.id=ci.media_id)"
            "  WHEN 'tv_show' THEN (SELECT substr(s.first_air_date,1,4) FROM tv_shows s WHERE s.id=ci.media_id)"
            "  WHEN 'album' THEN (SELECT al.year FROM music_albums al WHERE al.id=ci.media_id)"
            " END AS year,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type=ci.media_type"
            "  AND a.owner_id=ci.media_id AND a.kind IN ('poster','album_cover') AND a.local_path<>''"
            "  LIMIT 1) AS poster_path"
            " FROM collection_items ci WHERE ci.collection_id=?"
            " ORDER BY ci.position",
            (collection_id,),
        )
        return [dict(r) for r in rows if r["title"]]

    def reorder(self, collection_id: int, ordered_ids: list[tuple[str, int]]) -> None:
        with self.db.transaction() as conn:
            for position, (media_type, media_id) in enumerate(ordered_ids):
                conn.execute(
                    "UPDATE collection_items SET position=? WHERE collection_id=?"
                    " AND media_type=? AND media_id=?",
                    (position, collection_id, media_type, media_id),
                )

    def collections_containing(self, media_type: str, media_id: int) -> list[int]:
        rows = self.db.query(
            "SELECT collection_id FROM collection_items WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        return [r["collection_id"] for r in rows]
