from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database.connection import get_connection


class MediaRepository:
    """Database operations for media items and their files."""

    def create_media(
        self,
        *,
        media_type: str,
        title: str,
        year: int | None = None,
        path: str | None = None,
        file_size: int | None = None,
    ) -> int:
        with get_connection() as db:
            cursor = db.execute(
                """
                INSERT INTO media_items
                    (media_type, title, year, sort_title)
                VALUES (?, ?, ?, ?)
                """,
                (media_type, title, year, title.casefold()),
            )

            media_id = int(cursor.lastrowid)

            if path is not None:
                db.execute(
                    """
                    INSERT INTO media_files
                        (media_id, path, file_size)
                    VALUES (?, ?, ?)
                    """,
                    (media_id, str(Path(path)), file_size),
                )

            return media_id

    def get_media(self, media_id: int) -> dict[str, Any] | None:
        with get_connection() as db:
            row = db.execute(
                """
                SELECT *
                FROM media_items
                WHERE id = ?
                """,
                (media_id,),
            ).fetchone()

            if row is None:
                return None

            return dict(row)

    def get_media_files(self, media_id: int) -> list[dict[str, Any]]:
        with get_connection() as db:
            rows = db.execute(
                """
                SELECT *
                FROM media_files
                WHERE media_id = ?
                ORDER BY id
                """,
                (media_id,),
            ).fetchall()

            return [dict(row) for row in rows]

    def list_media(
        self,
        *,
        media_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        with get_connection() as db:
            if media_type:
                rows = db.execute(
                    """
                    SELECT *
                    FROM media_items
                    WHERE media_type = ?
                    ORDER BY sort_title, id
                    LIMIT ? OFFSET ?
                    """,
                    (media_type, limit, offset),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT *
                    FROM media_items
                    ORDER BY sort_title, id
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()

            return [dict(row) for row in rows]

    def count_media(self, media_type: str | None = None) -> int:
        with get_connection() as db:
            if media_type:
                row = db.execute(
                    """
                    SELECT COUNT(*)
                    FROM media_items
                    WHERE media_type = ?
                    """,
                    (media_type,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT COUNT(*) FROM media_items"
                ).fetchone()

            return int(row[0])

    def delete_media(self, media_id: int) -> bool:
        with get_connection() as db:
            cursor = db.execute(
                "DELETE FROM media_items WHERE id = ?",
                (media_id,),
            )
            return cursor.rowcount > 0
