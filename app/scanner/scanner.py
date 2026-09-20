"""
Real media file scanner.

The scanner identifies movies, music and TV episodes from
file names. Metadata lookup is intentionally separate.
"""

from datetime import datetime
from pathlib import Path
import re
from typing import List, Dict, Callable, Optional

from app.logging import get_logger

logger = get_logger("scanner")


VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".vob"
}

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".aac", ".m4a", ".ogg", ".wav", ".wma", ".opus"
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp"
}

# Images are artwork, not library media items.
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


EPISODE_RE = re.compile(
    r"(?i)(?:^|[.\s_-])S(?P<season>\d{1,2})E(?P<episode>\d{1,3})(?:$|[.\s_-])"
)

ALT_EPISODE_RE = re.compile(
    r"(?i)(?:^|[.\s_-])(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?:$|[.\s_-])"
)

YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

RELEASE_TAG_RE = re.compile(
    r"(?i)(?:^|[.\s_-])"
    r"(2160p|1080p|720p|576p|480p|360p|"
    r"4k|8k|"
    r"bluray|blu-ray|brrip|bdrip|webrip|web-dl|webdl|"
    r"hdtv|dvdrip|hdrip|"
    r"x264|x265|h264|h265|hevc|avc|"
    r"10bit|8bit|aac|ac3|dts|ddp|"
    r"proper|repack|remux|yify|rarbg|"
    r"extended|unrated)"
    r"(?:$|[.\s_-])"
)


def _normalize_title(value: str) -> str:
    value = value.strip(" ._-")
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    # 9.1.1 -> 9-1-1
    if re.fullmatch(r"\d+(?:\s+\d+)+", value):
        value = "-".join(value.split())

    return value


def parse_media_filename(filename: str) -> Dict:
    """
    Parse a media filename.

    Examples:
      The.Matrix.1999.1080p.mkv
      Breaking.Bad.S01E01.mkv
      9.1.1.S02E02.720p.mkv
      Show.1x02.mkv
    """

    stem = Path(filename).stem

    episode_match = EPISODE_RE.search(stem)
    if not episode_match:
        episode_match = ALT_EPISODE_RE.search(stem)

    if episode_match:
        season = int(episode_match.group("season"))
        episode = int(episode_match.group("episode"))

        title_part = stem[:episode_match.start()]

        year_matches = list(YEAR_RE.finditer(title_part))
        year_match = year_matches[-1] if year_matches else None
        if year_match:
            title_part = title_part[:year_match.start()]

        title_part = RELEASE_TAG_RE.sub(" ", title_part)
        title = _normalize_title(title_part)

        return {
            "media_type": "episode",
            "title": title or stem,
            "year": None,
            "season_number": season,
            "episode_number": episode,
            "episode_title": None,
        }

    year_matches = list(YEAR_RE.finditer(stem))
    year_match = year_matches[-1] if year_matches else None
    year = int(year_match.group(1)) if year_match else None

    title_part = stem

    if year_match:
        title_part = title_part[:year_match.start()]

    title_part = RELEASE_TAG_RE.sub(" ", title_part)
    title = _normalize_title(title_part)

    if not title:
        title = _normalize_title(stem)

    return {
        "media_type": "movie",
        "title": title,
        "year": year,
        "season_number": None,
        "episode_number": None,
        "episode_title": None,
    }


def extract_year_and_clean_title(filename: str):
    """Compatibility helper for older callers."""
    parsed = parse_media_filename(filename)
    return parsed["title"], parsed.get("year")


def get_media_type(extension: str) -> str:
    ext = extension.lower()

    if ext in VIDEO_EXTENSIONS:
        return "movie"
    if ext in AUDIO_EXTENSIONS:
        return "music"
    return "other"


def classify_video_file(filename: str, full_path: str = "") -> str:
    """Compatibility wrapper."""
    return parse_media_filename(filename)["media_type"]


def scan_directory(
    directory: str,
    progress_callback: Optional[Callable] = None,
    cancel_callback: Optional[Callable] = None
) -> List[Dict]:

    results = []
    path = Path(directory)

    if not path.exists():
        logger.error(f"Directory does not exist: {directory}")
        return results

    if not path.is_dir():
        logger.error(f"Path is not a directory: {directory}")
        return results

    logger.info(f"Starting scan of {directory}...")

    all_files = list(path.rglob("*"))
    total_files = sum(1 for f in all_files if f.is_file())

    processed = 0
    errors = 0

    for file_path in all_files:
        if cancel_callback and cancel_callback():
            logger.info("Scan cancelled by user")
            break

        if not file_path.is_file():
            continue

        processed += 1

        if progress_callback:
            progress_callback(
                processed,
                total_files,
                str(file_path)
            )

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            stat = file_path.stat()

            if file_path.suffix.lower() in VIDEO_EXTENSIONS:
                parsed = parse_media_filename(file_path.name)
            else:
                parsed = {
                    "media_type": get_media_type(file_path.suffix),
                    "title": file_path.stem,
                    "year": None,
                    "season_number": None,
                    "episode_number": None,
                    "episode_title": None,
                }

            results.append({
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_size": stat.st_size,
                "file_format": file_path.suffix.lstrip(".").upper(),
                "media_type": parsed["media_type"],
                "title": parsed["title"],
                "year": parsed["year"],
                "season_number": parsed["season_number"],
                "episode_number": parsed["episode_number"],
                "episode_title": parsed["episode_title"],
                "modified_at": datetime.fromtimestamp(stat.st_mtime),
            })

        except Exception as e:
            errors += 1
            logger.error(f"Error processing {file_path}: {e}")

    logger.info(
        f"Scan complete: {len(results)} media files found, {errors} errors"
    )

    return results
