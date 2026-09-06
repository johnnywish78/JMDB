"""Movie matching: video files that are not episodes → movie candidates."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from app.library.media_detector import (
    MULTI_PART,
    detect_quality,
    extract_year,
    strip_release_noise,
)
from app.library.series_matcher import normalize_show_title


@dataclass
class MovieCandidate:
    title: str
    year: int | None
    part: int | None = None
    quality: str = ""
    file_id: int = 0
    path: str = ""
    filename: str = ""
    size_bytes: int = 0


def parse_movie_stem(stem: str) -> tuple[str, int | None, int | None]:
    """Return (title, year, part) from a filename stem."""
    part_match = MULTI_PART.search(stem)
    part = int(part_match.group(1)) if part_match else None
    if part_match:
        stem = stem[: part_match.start()]
    title, year = extract_year(stem)
    title = strip_release_noise(title)
    return title, year, part


def _movie_title_from_dir(dir_name: str) -> tuple[str, int | None]:
    """'Movie Name (2024)' → ('Movie Name', 2024)."""
    title, year = extract_year(dir_name)
    return strip_release_noise(title), year


def candidates_from_files(records: list[dict]) -> list[MovieCandidate]:
    """Build movie candidates from file records.

    ``records`` are dicts with keys: id, path, filename, directory, size_bytes.
    Directory names carry a lot of signal ('Movie Name (2024)/movie.1080p.mkv'),
    so a well-formed parent directory wins over a noisy filename.
    """
    candidates: list[MovieCandidate] = []
    for record in records:
        stem = record["filename"].rsplit(".", 1)[0]
        file_title, file_year, part = parse_movie_stem(stem)

        parent_name = record["directory"].rstrip("/").rsplit("/", 1)[-1]
        dir_title, dir_year = _movie_title_from_dir(parent_name)

        # Prefer the source that yields a title with a year.
        title, year = file_title, file_year
        if (not title or year is None) and dir_title and dir_year:
            title, year = dir_title, dir_year
        elif dir_title and dir_year and file_year != dir_year and normalize_show_title(dir_title) == normalize_show_title(file_title):
            title, year = dir_title, dir_year
        if not title and dir_title:
            title, year = dir_title, dir_year
        if not title:
            continue

        candidates.append(
            MovieCandidate(
                title=title,
                year=year,
                part=part,
                quality=detect_quality(record["filename"]),
                file_id=record["id"],
                path=record["path"],
                filename=record["filename"],
                size_bytes=record["size_bytes"],
            )
        )
    return candidates


def group_movies(candidates: list[MovieCandidate]) -> dict[tuple[str, int | None], list[MovieCandidate]]:
    """Group candidates that describe the same movie.

    Keyed by (normalized title, year). Multi-part files (Part 1/CD2) group
    under the same movie; the largest file becomes the primary.
    """
    groups: dict[tuple[str, int | None], list[MovieCandidate]] = defaultdict(list)
    for candidate in candidates:
        key = (normalize_show_title(candidate.title), candidate.year)
        groups[key].append(candidate)
    return dict(groups)


def primary_file(candidates: list[MovieCandidate]) -> MovieCandidate:
    return max(candidates, key=lambda c: c.size_bytes)
