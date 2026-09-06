"""Music matching: audio files → artists / albums / tracks.

Tags (mutagen) are authoritative when present; directory structure
(Artist/Album/01 - Title.ext) is the fallback.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import PurePath

logger = logging.getLogger(__name__)

TRACK_NUMBER_RE = re.compile(r"^\s*(\d{1,3})\s*[-._)\]]\s*(.+)$")
DISC_NUMBER_RE = re.compile(r"(?i)(?:^|[\s_\-])(?:cd|disc)\s*([0-9]{1,2})(?:[\s_\-]|$)")


@dataclass
class TrackCandidate:
    artist: str
    album: str
    title: str
    track_number: int | None = None
    disc_number: int | None = None
    duration_seconds: int | None = None
    album_year: int | None = None
    file_id: int = 0
    path: str = ""
    filename: str = ""
    size_bytes: int = 0
    genre: str = ""


def _parse_with_tags(path: str) -> dict:
    """Read tags with mutagen; returns {} when unavailable."""
    try:
        import mutagen

        audio = mutagen.File(path, easy=True)
        if audio is None:
            return {}
        tags = {}
        for key in ("artist", "album", "title", "genre"):
            value = audio.tags.get(key) if audio.tags else None
            if isinstance(value, list) and value:
                tags[key] = str(value[0])
            elif value:
                tags[key] = str(value)
        tracknumber = audio.tags.get("tracknumber") if audio.tags else None
        if isinstance(tracknumber, list) and tracknumber:
            match = re.match(r"\s*(\d+)", str(tracknumber[0]))
            if match:
                tags["track_number"] = int(match.group(1))
        discnumber = audio.tags.get("discnumber") if audio.tags else None
        if isinstance(discnumber, list) and discnumber:
            match = re.match(r"\s*(\d+)", str(discnumber[0]))
            if match:
                tags["disc_number"] = int(match.group(1))
        if getattr(audio, "info", None) is not None and audio.info.length:
            tags["duration_seconds"] = int(round(audio.info.length))
        date = audio.tags.get("date") if audio.tags else None
        if isinstance(date, list) and date:
            year_match = re.search(r"(\d{4})", str(date[0]))
            if year_match:
                tags["year"] = int(year_match.group(1))
        return tags
    except Exception as exc:  # corrupted file, unsupported format…
        logger.debug("tag read failed for %s: %s", path, exc)
        return {}


def _split_parent(path: str) -> tuple[str, str]:
    """Return (parent_dir_name, grandparent_dir_name)."""
    pure = PurePath(path)
    parent = pure.parent.name
    grandparent = pure.parent.parent.name
    return parent, grandparent


def candidate_from_file(record: dict) -> TrackCandidate | None:
    """Build a track candidate; artist/album resolution order:

    1. tags (most accurate)
    2. 'Artist - Title.ext' single-directory layout
    3. 'Artist/Album/01 Title.ext' nested layout
    """
    path = record["path"]
    filename = record["filename"]
    stem = filename.rsplit(".", 1)[0]
    tags = _parse_with_tags(path) if record.get("size_bytes", 0) > 0 else {}
    if not tags and record.get("size_bytes", 0) > 0:
        tags = _parse_with_tags(path)

    artist = tags.get("artist", "")
    album = tags.get("album", "")
    title = tags.get("title", "")
    track_number = tags.get("track_number")
    disc_number = tags.get("disc_number")
    duration = tags.get("duration_seconds")
    year = tags.get("year")
    genre = tags.get("genre", "")

    parent, grandparent = _split_parent(path)

    if not album:
        # 'Artist/Album/01 - Title.ext' layout: the parent directory is the album
        if parent and not re.match(r"^\d", parent):
            album = parent
    if not artist:
        dash = re.split(r"\s+-\s+", stem, maxsplit=1)
        if len(dash) == 2 and not re.match(r"^\d+$", dash[0].strip()):
            artist = dash[0].strip()
        elif grandparent and not re.match(r"^\d", grandparent):
            artist = grandparent  # Artist/Album/track layout
    if not title:
        match = TRACK_NUMBER_RE.match(stem)
        if match:
            if track_number is None:
                track_number = int(match.group(1))
            title = match.group(2).strip()
        else:
            title = stem.strip()
    if track_number is None:
        match = re.match(r"^(\d{1,3})[\s._\-]+", stem)
        if match:
            track_number = int(match.group(1))
    if disc_number is None:
        match = DISC_NUMBER_RE.search(parent) or DISC_NUMBER_RE.search(stem)
        if match:
            disc_number = int(match.group(1))

    title = title.strip(" -_.")
    artist = artist.strip(" -_.")
    album = album.strip(" -_.")
    if not title or not artist:
        return None

    return TrackCandidate(
        artist=artist,
        album=album or "Unknown Album",
        title=title,
        track_number=track_number,
        disc_number=disc_number,
        duration_seconds=duration,
        album_year=year,
        file_id=record["id"],
        path=path,
        filename=filename,
        size_bytes=record.get("size_bytes", 0),
        genre=genre,
    )
