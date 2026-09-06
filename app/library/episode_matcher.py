"""Episode matching: turn video filenames into (show, season, episode) candidates."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.library.media_detector import (
    ParsedName,
    detect_quality,
    extract_year,
    strip_release_noise,
)

SEASON_DIR_PATTERNS = [
    re.compile(r"(?i)^season[\s._\-]*(\d{1,2})$"),
    re.compile(r"(?i)^s(\d{1,2})$"),
    re.compile(r"(?i)^season[\s._\-]*(\d{1,2})\b"),
    re.compile(r"(?i)^(?:the\s+)?(?:series|serie)[\s._\-]*(\d{1,2})$"),
    re.compile(r"(?i)^specials?$"),
]


@dataclass
class EpisodeCandidate:
    show_title: str
    season: int
    episode: int
    episode_end: int | None = None
    year: int | None = None
    part: int | None = None
    quality: str = ""
    file_id: int = 0
    path: str = ""
    filename: str = ""
    size_bytes: int = 0
    title_hint: str = ""  # "Show - 2x05 - Episode Title" → "Episode Title"


def season_from_directory(dir_name: str) -> int | None:
    for pattern in SEASON_DIR_PATTERNS:
        match = pattern.match(dir_name.strip())
        if match:
            if match.group(1) is None or not match.group(1).isdigit():
                return 0  # specials
            return int(match.group(1))
    return None


def _episode_title_hint(stem: str, pattern_end: int) -> str:
    """Text after the episode marker often is the episode title."""
    tail = stem[pattern_end:].strip(" -_.")
    tail = strip_release_noise(tail)
    return tail


def parse_episode(stem: str, parent_dir: str = "", grandparent_dir: str = "") -> ParsedName | None:
    """Parse a filename stem into episode info, using directory context.

    Returns None when the file is not recognizable as an episode.
    """
    padded = f" {stem.strip()} "
    season_from_dir = season_from_directory(parent_dir) if parent_dir else None

    # 1) SxxEyy (possibly multi: S01E02E03)
    match = re.search(r"(?i)[\s._\-\[(]s(\d{1,2})[\s._\-]?e(\d{1,3})(?:[\s._\-]?e(\d{1,3}))?[\s._\-\])]", padded)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        end = int(match.group(3)) if match.group(3) else None
        title_part = padded[: match.start()]
        show = _clean_show_title(title_part) or _clean_show_title(parent_dir) or _clean_show_title(grandparent_dir)
        return ParsedName(
            title=show, season=season, episode=episode, episode_end=end,
            quality=detect_quality(stem),
        )

    # 2) 2x05
    match = re.search(r"(?i)(?:^|[\s._\-\[(])(\d{1,2})x(\d{1,3})(?:[\s._\-\])]|$)", padded)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        title_part = padded[: match.start()]
        show = _clean_show_title(title_part) or _clean_show_title(parent_dir) or _clean_show_title(grandparent_dir)
        return ParsedName(title=show, season=season, episode=episode, quality=detect_quality(stem))

    # 3) "Season 2 Episode 5"
    match = re.search(r"(?i)season[\s._\-]*(\d{1,2})[\s._\-]*episode[\s._\-]*(\d{1,3})", padded)
    if match:
        season, episode = int(match.group(1)), int(match.group(2))
        title_part = padded[: match.start()]
        show = _clean_show_title(title_part) or _clean_show_title(grandparent_dir) or _clean_show_title(parent_dir)
        return ParsedName(title=show, season=season, episode=episode, quality=detect_quality(stem))

    # 4) "Episode 5" — needs a season from the parent directory
    match = re.search(r"(?i)(?:^|[\s._\-])episode[\s._\-]*(\d{1,3})(?:[\s._\-]|$)", padded)
    if match and season_from_dir is not None:
        episode = int(match.group(1))
        title_part = padded[: match.start()]
        show = (
            _clean_show_title(title_part)
            or _clean_show_title(grandparent_dir)
            or _clean_show_title(parent_dir)
        )
        return ParsedName(title=show, season=season_from_dir, episode=episode, quality=detect_quality(stem))

    # 5) "Ep 5" — season from parent directory
    match = re.search(r"(?i)(?:^|[\s._\-])ep[\s._\-]*(\d{1,3})(?:[\s._\-]|$)", padded)
    if match and season_from_dir is not None:
        episode = int(match.group(1))
        title_part = padded[: match.start()]
        show = (
            _clean_show_title(title_part)
            or _clean_show_title(grandparent_dir)
            or _clean_show_title(parent_dir)
        )
        return ParsedName(title=show, season=season_from_dir, episode=episode, quality=detect_quality(stem))

    # 6) Bare "205" numeric run with a season-directory context (e.g. "Show.205")
    if season_from_dir is not None:
        match = re.search(r"(?:^|[\s._\-])(\d)(\d{2})(?:[\s._\-]|$)", padded)
        if match:
            episode = int(match.group(1) + match.group(2))
            title_part = padded[: match.start()]
            show = _clean_show_title(title_part) or _clean_show_title(grandparent_dir)
            return ParsedName(title=show, season=season_from_dir, episode=episode, quality=detect_quality(stem))

    return None


def _clean_show_title(text: str) -> str:
    if not text:
        return ""
    cleaned = strip_release_noise(text)
    # strip trailing year if present (show names rarely need it for matching)
    title, year = extract_year(cleaned)
    title = title.strip(" -_.")
    return title


def candidate_from_file(
    stem: str,
    parent_dir_name: str,
    grandparent_dir_name: str,
    file_id: int,
    path: str,
    filename: str,
    size_bytes: int,
) -> list[EpisodeCandidate]:
    """Build one or more candidates (multi-episode files yield several)."""
    parsed = parse_episode(stem, parent_dir_name, grandparent_dir_name)
    if parsed is None or not parsed.title or parsed.season is None or parsed.episode is None:
        return []
    year = parsed.year
    if year is None:
        _, year = extract_year(parent_dir_name)
    candidates = []
    end = parsed.episode_end or parsed.episode
    for episode in range(parsed.episode, end + 1):
        candidates.append(
            EpisodeCandidate(
                show_title=parsed.title,
                season=parsed.season,
                episode=episode,
                year=year,
                quality=parsed.quality,
                file_id=file_id,
                path=path,
                filename=filename,
                size_bytes=size_bytes,
            )
        )
    return candidates
