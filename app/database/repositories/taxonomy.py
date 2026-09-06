"""Genres, studios, networks, tags, and their associations."""
from __future__ import annotations

from app.domain.models import Genre, Network, Studio, Tag
from app.database.repositories import BaseRepository, row_to_dataclass


class TaxonomyRepository(BaseRepository):
    # -- genres -----------------------------------------------------------
    def genre_id(self, name: str) -> int:
        name = name.strip()
        cur = self.db.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (name,))
        if cur.lastrowid:
            return int(cur.lastrowid)
        return int(self.db.scalar("SELECT id FROM genres WHERE name=?", (name,)))

    def set_genres(self, media_type: str, media_id: int, names: list[str]) -> None:
        self.db.execute(
            "DELETE FROM media_genres WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        for name in names:
            if not name:
                continue
            gid = self.genre_id(name)
            self.db.execute(
                "INSERT OR IGNORE INTO media_genres (media_type, media_id, genre_id) VALUES (?,?,?)",
                (media_type, media_id, gid),
            )

    def genres_for(self, media_type: str, media_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT g.name FROM genres g JOIN media_genres mg ON mg.genre_id=g.id"
            " WHERE mg.media_type=? AND mg.media_id=? ORDER BY g.name",
            (media_type, media_id),
        )
        return [r["name"] for r in rows]

    def all_genres(self) -> list[Genre]:
        return [
            row_to_dataclass(r, Genre)
            for r in self.db.query("SELECT * FROM genres ORDER BY name")
        ]

    def genre_counts(self, media_type: str | None = None) -> list[tuple[str, int]]:
        if media_type:
            rows = self.db.query(
                "SELECT g.name, COUNT(*) n FROM genres g"
                " JOIN media_genres mg ON mg.genre_id=g.id WHERE mg.media_type=?"
                " GROUP BY g.name ORDER BY n DESC",
                (media_type,),
            )
        else:
            rows = self.db.query(
                "SELECT g.name, COUNT(*) n FROM genres g"
                " JOIN media_genres mg ON mg.genre_id=g.id"
                " GROUP BY g.name ORDER BY n DESC"
            )
        return [(r["name"], r["n"]) for r in rows]

    # -- studios ------------------------------------------------------------
    def studio_id(self, name: str) -> int:
        name = name.strip()
        cur = self.db.execute("INSERT OR IGNORE INTO studios (name) VALUES (?)", (name,))
        if cur.lastrowid:
            return int(cur.lastrowid)
        return int(self.db.scalar("SELECT id FROM studios WHERE name=?", (name,)))

    def set_studios(self, media_type: str, media_id: int, names: list[str]) -> None:
        self.db.execute(
            "DELETE FROM media_studios WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        for name in names:
            if name:
                self.db.execute(
                    "INSERT OR IGNORE INTO media_studios (media_type, media_id, studio_id) VALUES (?,?,?)",
                    (media_type, media_id, self.studio_id(name)),
                )

    def studios_for(self, media_type: str, media_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT s.name FROM studios s JOIN media_studios ms ON ms.studio_id=s.id"
            " WHERE ms.media_type=? AND ms.media_id=? ORDER BY s.name",
            (media_type, media_id),
        )
        return [r["name"] for r in rows]

    # -- networks -------------------------------------------------------------
    def network_id(self, name: str) -> int:
        name = name.strip()
        cur = self.db.execute("INSERT OR IGNORE INTO networks (name) VALUES (?)", (name,))
        if cur.lastrowid:
            return int(cur.lastrowid)
        return int(self.db.scalar("SELECT id FROM networks WHERE name=?", (name,)))

    def set_networks(self, tv_show_id: int, names: list[str]) -> None:
        self.db.execute("DELETE FROM show_networks WHERE tv_show_id=?", (tv_show_id,))
        for name in names:
            if name:
                self.db.execute(
                    "INSERT OR IGNORE INTO show_networks (tv_show_id, network_id) VALUES (?,?)",
                    (tv_show_id, self.network_id(name)),
                )

    def networks_for(self, tv_show_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT n.name FROM networks n JOIN show_networks sn ON sn.network_id=n.id"
            " WHERE sn.tv_show_id=? ORDER BY n.name",
            (tv_show_id,),
        )
        return [r["name"] for r in rows]

    # -- tags -------------------------------------------------------------------
    def tag_id(self, name: str) -> int:
        name = name.strip()
        cur = self.db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        if cur.lastrowid:
            return int(cur.lastrowid)
        return int(self.db.scalar("SELECT id FROM tags WHERE name=?", (name,)))

    def set_tags(self, media_type: str, media_id: int, names: list[str]) -> None:
        self.db.execute(
            "DELETE FROM media_tags WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        for name in names:
            if name:
                self.db.execute(
                    "INSERT OR IGNORE INTO media_tags (media_type, media_id, tag_id) VALUES (?,?,?)",
                    (media_type, media_id, self.tag_id(name)),
                )

    def tags_for(self, media_type: str, media_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT t.name FROM tags t JOIN media_tags mt ON mt.tag_id=t.id"
            " WHERE mt.media_type=? AND mt.media_id=? ORDER BY t.name",
            (media_type, media_id),
        )
        return [r["name"] for r in rows]
