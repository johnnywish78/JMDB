"""Duplicate detection over indexed media files."""
from __future__ import annotations

from dataclasses import dataclass

from app.database.repositories import Repositories


@dataclass
class DuplicateGroup:
    checksum: str
    files: list[dict]  # {id, path, filename, size_bytes, library_location_id}

    @property
    def size_bytes(self) -> int:
        return self.files[0]["size_bytes"] if self.files else 0


class DuplicateDetector:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def groups(self, min_size_mb: int = 50) -> list[DuplicateGroup]:
        """Duplicate groups among checksummed files."""
        raw_groups = self.repos.files.duplicate_groups(min_size_bytes=min_size_mb * 1024 * 1024)
        out = []
        for media_files in raw_groups:
            out.append(
                DuplicateGroup(
                    checksum=media_files[0].checksum or "",
                    files=[
                        {
                            "id": mf.id,
                            "path": mf.path,
                            "filename": mf.filename,
                            "size_bytes": mf.size_bytes,
                            "library_location_id": mf.library_location_id,
                        }
                        for mf in media_files
                    ],
                )
            )
        return out

    def wasted_bytes(self, min_size_mb: int = 50) -> int:
        return sum(
            (len(g.files) - 1) * g.size_bytes for g in self.groups(min_size_mb)
        )
