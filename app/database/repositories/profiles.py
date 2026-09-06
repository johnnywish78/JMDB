"""Profiles (users) repository."""
from __future__ import annotations

from app.domain.models import Profile
from app.database.repositories import BaseRepository, rows_to_dataclasses


class ProfilesRepository(BaseRepository):
    def ensure_default(self) -> Profile:
        row = self.db.query_one("SELECT * FROM profiles WHERE is_default=1")
        if row is None:
            row = self.db.query_one(
                "SELECT * FROM profiles ORDER BY id LIMIT 1"
            )
        if row is None:
            self.db.execute("INSERT INTO profiles (name, is_default) VALUES ('Default', 1)")
            row = self.db.query_one("SELECT * FROM profiles WHERE is_default=1")
        return rows_to_dataclasses([row], Profile)[0]

    def list(self) -> list[Profile]:
        return rows_to_dataclasses(
            self.db.query("SELECT * FROM profiles ORDER BY id"), Profile
        )

    def get(self, profile_id: int) -> Profile | None:
        row = self.db.query_one("SELECT * FROM profiles WHERE id=?", (profile_id,))
        return rows_to_dataclasses([row], Profile)[0] if row else None

    def create(self, name: str) -> Profile:
        cur = self.db.execute("INSERT INTO profiles (name) VALUES (?)", (name,))
        return Profile(id=cur.lastrowid, name=name)

    def rename(self, profile_id: int, name: str) -> None:
        self.db.execute("UPDATE profiles SET name=? WHERE id=?", (name, profile_id))

    def delete(self, profile_id: int) -> None:
        # never delete the last profile
        if self.db.scalar("SELECT COUNT(*) FROM profiles") <= 1:
            raise ValueError("cannot delete the only profile")
        if self.db.scalar("SELECT is_default FROM profiles WHERE id=?", (profile_id,)):
            raise ValueError("cannot delete the default profile")
        self.db.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
