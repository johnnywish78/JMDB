"""People and credits repository."""
from __future__ import annotations

from app.domain.models import Credit, Person
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses

PERSON_PHOTO_SUB = (
    "(SELECT a.local_path FROM artwork a WHERE a.owner_type='person' AND a.owner_id=p.id"
    " AND a.kind='profile' AND a.local_path<>'' ORDER BY a.id LIMIT 1) AS photo_path"
)


class PeopleRepository(BaseRepository):
    # -- people -----------------------------------------------------------------
    def get(self, person_id: int) -> Person | None:
        row = self.db.query_one("SELECT * FROM people WHERE id=?", (person_id,))
        return row_to_dataclass(row, Person) if row else None

    def find_by_name(self, name: str) -> Person | None:
        row = self.db.query_one("SELECT * FROM people WHERE lower(name)=lower(?) LIMIT 1", (name,))
        return row_to_dataclass(row, Person) if row else None

    def get_or_create(self, name: str, **values) -> int:
        name = name.strip()
        if not name:
            raise ValueError("person name required")
        row = self.db.query_one("SELECT id FROM people WHERE lower(name)=lower(?)", (name,))
        if row:
            return int(row["id"])
        allowed = {"biography", "birthday", "deathday", "place_of_birth", "popularity"}
        cols = ["name"]
        params: list = [name]
        for key, value in values.items():
            if key in allowed and value is not None:
                cols.append(key)
                params.append(value)
        cur = self.db.execute(
            f"INSERT INTO people ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            params,
        )
        return int(cur.lastrowid)

    def update(self, person_id: int, values: dict) -> None:
        allowed = {"name", "biography", "birthday", "deathday", "place_of_birth", "popularity"}
        sets, params = [], []
        for key, value in values.items():
            if key in allowed and value is not None:
                sets.append(f"{key}=?")
                params.append(value)
        if sets:
            params.append(person_id)
            self.db.execute(f"UPDATE people SET {', '.join(sets)} WHERE id=?", params)

    def count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM people") or 0)

    def list_page(self, page: int = 0, per_page: int = 60, query: str = "") -> tuple[list[dict], int]:
        where, params = ["1=1"], []
        if query:
            where.append("p.name LIKE ?")
            params.append(f"%{query}%")
        base = " AND ".join(where)
        total = int(self.db.scalar(f"SELECT COUNT(*) FROM people p WHERE {base}", params) or 0)
        rows = self.db.query(
            f"SELECT p.id, p.name, {PERSON_PHOTO_SUB},"
            " (SELECT COUNT(*) FROM credits c WHERE c.person_id=p.id) AS credit_count"
            f" FROM people p WHERE {base}"
            " ORDER BY credit_count DESC, p.name COLLATE NOCASE LIMIT ? OFFSET ?",
            (*params, per_page, page * per_page),
        )
        return [dict(r) for r in rows], total

    def search(self, query: str, limit: int = 30) -> list[dict]:
        rows = self.db.query(
            f"SELECT p.id, p.name, {PERSON_PHOTO_SUB} FROM people p WHERE p.name LIKE ?"
            " ORDER BY p.name COLLATE NOCASE LIMIT ?",
            (f"%{query}%", limit),
        )
        return [dict(r) for r in rows]

    # -- credits -------------------------------------------------------------------
    def add_credit(
        self,
        person_id: int,
        media_type: str,
        media_id: int,
        role: str,
        character: str = "",
        job: str = "",
        sort_order: int = 0,
    ) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO credits (person_id, media_type, media_id, role, character, job, sort_order)"
            " VALUES (?,?,?,?,?,?,?)",
            (person_id, media_type, media_id, role, character, job, sort_order),
        )

    def credits_for(self, media_type: str, media_id: int) -> list[Credit]:
        rows = self.db.query(
            "SELECT c.* FROM credits c WHERE c.media_type=? AND c.media_id=?"
            " ORDER BY c.sort_order, c.id",
            (media_type, media_id),
        )
        return rows_to_dataclasses(rows, Credit)

    def credits_with_people(self, media_type: str, media_id: int) -> list[dict]:
        rows = self.db.query(
            f"SELECT c.person_id, c.role, c.character, c.job, c.sort_order, p.name, {PERSON_PHOTO_SUB}"
            " FROM credits c JOIN people p ON p.id=c.person_id"
            " WHERE c.media_type=? AND c.media_id=?"
            " ORDER BY c.sort_order, c.id",
            (media_type, media_id),
        )
        return [dict(r) for r in rows]

    def replace_credits(self, media_type: str, media_id: int, credits: list[dict]) -> None:
        """Atomically replace the credit list of one media item."""
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM credits WHERE media_type=? AND media_id=?", (media_type, media_id)
            )
            for credit in credits:
                person_id = self.get_or_create(credit.get("name", ""))
                if not person_id:
                    continue
                if credit.get("biography") or credit.get("place_of_birth"):
                    self.update(person_id, {k: v for k, v in credit.items() if k in ("biography", "place_of_birth", "birthday")})
                conn.execute(
                    "INSERT OR IGNORE INTO credits (person_id, media_type, media_id, role, character, job, sort_order)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (
                        person_id, media_type, media_id,
                        credit.get("role", "crew"), credit.get("character", ""),
                        credit.get("job", ""), credit.get("sort_order", 0),
                    ),
                )

    def filmography(self, person_id: int) -> list[dict]:
        """All credits joined to their media titles and posters."""
        rows = self.db.query(
            "SELECT c.role, c.character, c.job, c.media_type, c.media_id,"
            " CASE c.media_type WHEN 'movie' THEN (SELECT m.title FROM movies m WHERE m.id=c.media_id)"
            "                    WHEN 'tv_show' THEN (SELECT s.title FROM tv_shows s WHERE s.id=c.media_id)"
            "                    WHEN 'episode' THEN (SELECT s2.title||' '||e.season_number||'x'||e.episode_number"
            "                        FROM episodes e JOIN tv_shows s2 ON s2.id=e.tv_show_id WHERE e.id=c.media_id) END AS media_title,"
            " CASE c.media_type WHEN 'movie' THEN (SELECT m.year FROM movies m WHERE m.id=c.media_id)"
            "                    WHEN 'tv_show' THEN (SELECT substr(s.first_air_date,1,4) FROM tv_shows s WHERE s.id=c.media_id) END AS media_year,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type=c.media_type AND a.owner_id=c.media_id"
            "  AND a.kind IN ('poster') AND a.local_path<>'' LIMIT 1) AS poster_path"
            " FROM credits c WHERE c.person_id=?"
            " ORDER BY media_year DESC",
            (person_id,),
        )
        return [dict(r) for r in rows if r["media_title"]]

    def top_people(self, role: str, limit: int = 10) -> list[tuple[str, int]]:
        rows = self.db.query(
            "SELECT p.name, COUNT(*) n FROM credits c JOIN people p ON p.id=c.person_id"
            " WHERE c.role=? AND c.media_type IN ('movie','tv_show')"
            " GROUP BY p.name ORDER BY n DESC LIMIT ?",
            (role, limit),
        )
        return [(r["name"], r["n"]) for r in rows]
