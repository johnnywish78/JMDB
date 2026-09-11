from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.database.connection import get_connection
from app.database.repositories.media import MediaRepository


VIDEO_EXTENSIONS = {
    ".avi",
    ".divx",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ts",
    ".webm",
    ".wmv",
}

YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
EPISODE_RE = re.compile(
    r"(?i)(?:^|[\s._-])S(?P<season>\d{1,2})"
    r"(?:E(?P<episode>\d{1,3}))?"
)

SEPARATORS_RE = re.compile(r"[._]+")


@dataclass(frozen=True)
class ParsedMedia:
    title: str
    year: int | None
    media_type: str
    season: int | None = None
    episode: int | None = None


@dataclass
class ScanResult:
    scanned: int = 0
    added: int = 0
    skipped: int = 0
    errors: int = 0


class LibraryScanner:
    """Scan library paths and register video files in the database."""

    def __init__(self, media_repository: MediaRepository | None = None):
        self.media_repository = media_repository or MediaRepository()

    def scan_path(self, root: str | Path) -> ScanResult:
        root_path = Path(root).expanduser().resolve()

        result = ScanResult()

        if not root_path.exists() or not root_path.is_dir():
            result.errors = 1
            return result

        for path in root_path.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix.casefold() not in VIDEO_EXTENSIONS:
                continue

            result.scanned += 1

            try:
                normalized = str(path.resolve())

                if self._file_exists(normalized):
                    result.skipped += 1
                    continue

                parsed = parse_media_filename(path)

                self.media_repository.create_media(
                    media_type=parsed.media_type,
                    title=parsed.title,
                    year=parsed.year,
                    path=normalized,
                    file_size=path.stat().st_size,
                )

                result.added += 1

            except (OSError, ValueError):
                result.errors += 1

        return result

    def _file_exists(self, path: str) -> bool:
        with get_connection() as db:
            row = db.execute(
                """
                SELECT 1
                FROM media_files
                WHERE path = ?
                LIMIT 1
                """,
                (path,),
            ).fetchone()

            return row is not None


def parse_media_filename(path: str | Path) -> ParsedMedia:
    """Extract a conservative title/year/type hint from a media filename."""

    file_path = Path(path)
    name = file_path.stem

    episode_match = EPISODE_RE.search(name)

    season: int | None = None
    episode: int | None = None
    media_type = "movie"

    if episode_match:
        media_type = "series"
        season = int(episode_match.group("season"))

        if episode_match.group("episode") is not None:
            episode = int(episode_match.group("episode"))

    year_match = YEAR_RE.search(name)
    year = int(year_match.group(1)) if year_match else None

    title_part = name

    if episode_match:
        title_part = name[:episode_match.start()]
    elif year_match:
        title_part = name[:year_match.start()]

    title_part = SEPARATORS_RE.sub(" ", title_part)
    title_part = re.sub(r"[\[\](){}]", " ", title_part)
    title_part = re.sub(r"\s+", " ", title_part).strip()

    if not title_part:
        title_part = file_path.stem

    return ParsedMedia(
        title=title_part,
        year=year,
        media_type=media_type,
        season=season,
        episode=episode,
    )
