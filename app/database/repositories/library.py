from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database.connection import get_connection


class LibraryRepository:
    """Database operations for libraries and their filesystem paths."""

    def create_library(self, name: str) -> int:
        name = name.strip()

        if not name:
            raise ValueError("Library name cannot be empty")

        with get_connection() as db:
            cursor = db.execute(
                """
                INSERT INTO libraries (name)
                VALUES (?)
                """,
                (name,),
            )
            return int(cursor.lastrowid)

    def get_library(self, library_id: int) -> dict[str, Any] | None:
        with get_connection() as db:
            row = db.execute(
                """
                SELECT *
                FROM libraries
                WHERE id = ?
                """,
                (library_id,),
            ).fetchone()

            return dict(row) if row is not None else None

    def list_libraries(self) -> list[dict[str, Any]]:
        with get_connection() as db:
            rows = db.execute(
                """
                SELECT *
                FROM libraries
                ORDER BY name COLLATE NOCASE, id
                """
            ).fetchall()

            return [dict(row) for row in rows]

    def delete_library(self, library_id: int) -> bool:
        with get_connection() as db:
            cursor = db.execute(
                """
                DELETE FROM libraries
                WHERE id = ?
                """,
                (library_id,),
            )
            return cursor.rowcount > 0

    def add_path(self, library_id: int, path: str) -> int:
        normalized = str(Path(path).expanduser().resolve())

        with get_connection() as db:
            library = db.execute(
                """
                SELECT id
                FROM libraries
                WHERE id = ?
                """,
                (library_id,),
            ).fetchone()

            if library is None:
                raise ValueError(f"Library not found: {library_id}")

            cursor = db.execute(
                """
                INSERT INTO library_paths (library_id, path)
                VALUES (?, ?)
                """,
                (library_id, normalized),
            )
            return int(cursor.lastrowid)

    def get_paths(self, library_id: int) -> list[dict[str, Any]]:
        with get_connection() as db:
            rows = db.execute(
                """
                SELECT *
                FROM library_paths
                WHERE library_id = ?
                ORDER BY path COLLATE NOCASE, id
                """,
                (library_id,),
            ).fetchall()

            return [dict(row) for row in rows]

    def remove_path(self, path_id: int) -> bool:
        with get_connection() as db:
            cursor = db.execute(
                """
                DELETE FROM library_paths
                WHERE id = ?
                """,
                (path_id,),
            )
            return cursor.rowcount > 0

    def get_library_for_path(self, path: str) -> dict[str, Any] | None:
        normalized = str(Path(path).expanduser().resolve())

        with get_connection() as db:
            row = db.execute(
                """
                SELECT
                    l.id AS library_id,
                    l.name AS library_name,
                    lp.id AS path_id,
                    lp.path
                FROM library_paths lp
                JOIN libraries l ON l.id = lp.library_id
                WHERE lp.path = ?
                """,
                (normalized,),
            ).fetchone()

            return dict(row) if row is not None else None
