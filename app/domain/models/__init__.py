"""Domain entity dataclasses.

These are plain in-memory records mapped by the repository layer from SQLite
rows. They carry no persistence or UI concerns. ``id`` is ``None`` until a
row is inserted; all fields have defaults so entities can be constructed
partially before insertion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Profile:
    name: str = ""
    is_default: bool = False
    created_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class LibraryLocation:
    path: str = ""
    label: str = ""
    enabled: bool = True
    added_at: Optional[datetime] = None
    last_scan_at: Optional[datetime] = None
    last_scan_status: str = "never"
    last_scan_error: str = ""
    id: Optional[int] = None


@dataclass
class MediaFile:
    library_location_id: int = 0
    path: str = ""
    filename: str = ""
    directory: str = ""
    size_bytes: int = 0
    mtime_ns: int = 0
    kind: str = "video"  # MediaKind value
    container: str = ""
    checksum: str = ""
    is_missing: bool = False
    indexed_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    probe: Optional[dict[str, Any]] = None  # ffprobe/ffmpeg-derived info
    id: Optional[int] = None

    @property
    def stem(self) -> str:
        from pathlib import PurePath

        return PurePath(self.filename).stem


@dataclass
class Movie:
    title: str = ""
    original_title: str = ""
    sort_title: str = ""
    year: Optional[int] = None
    release_date: Optional[str] = None
    runtime_seconds: Optional[int] = None
    overview: str = ""
    tagline: str = ""
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    certification: str = ""
    languages: str = ""
    countries: str = ""
    collection_id: Optional[int] = None  # franchise (movie_collections)
    added_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class TvShow:
    title: str = ""
    original_title: str = ""
    sort_title: str = ""
    first_air_date: Optional[str] = None
    last_air_date: Optional[str] = None
    status: str = ""
    overview: str = ""
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    added_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class Season:
    tv_show_id: int = 0
    season_number: int = 0
    title: str = ""
    overview: str = ""
    air_date: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Episode:
    tv_show_id: int = 0
    season_id: int = 0
    season_number: int = 0
    episode_number: int = 0
    title: str = ""
    overview: str = ""
    air_date: Optional[str] = None
    runtime_seconds: Optional[int] = None
    rating: Optional[float] = None
    id: Optional[int] = None


@dataclass
class Person:
    name: str = ""
    biography: str = ""
    birthday: Optional[str] = None
    deathday: Optional[str] = None
    place_of_birth: str = ""
    popularity: Optional[float] = None
    id: Optional[int] = None


@dataclass
class Credit:
    person_id: int = 0
    media_type: str = ""  # movie | tv_show | episode
    media_id: int = 0
    role: str = ""  # CreditRole value
    character: str = ""
    job: str = ""
    sort_order: int = 0
    id: Optional[int] = None


@dataclass
class Genre:
    name: str = ""
    id: Optional[int] = None


@dataclass
class Studio:
    name: str = ""
    id: Optional[int] = None


@dataclass
class Network:
    name: str = ""
    id: Optional[int] = None


@dataclass
class MovieCollection:
    """A franchise/collection (e.g. a film series), sourced from providers."""

    name: str = ""
    overview: str = ""
    id: Optional[int] = None


@dataclass
class UserCollection:
    """A user-created collection of library items."""

    name: str = ""
    description: str = ""
    created_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class MusicArtist:
    name: str = ""
    sort_name: str = ""
    biography: str = ""
    disambiguation: str = ""
    id: Optional[int] = None


@dataclass
class MusicAlbum:
    artist_id: int = 0
    title: str = ""
    year: Optional[int] = None
    release_date: Optional[str] = None
    track_count: int = 0
    id: Optional[int] = None


@dataclass
class MusicTrack:
    album_id: int = 0
    artist_id: int = 0
    title: str = ""
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    duration_seconds: Optional[int] = None
    id: Optional[int] = None


@dataclass
class Playlist:
    profile_id: int = 0
    name: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class PlaybackState:
    profile_id: int = 0
    media_type: str = ""
    media_id: int = 0
    media_file_id: Optional[int] = None
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    updated_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class PlaybackHistoryEntry:
    profile_id: int = 0
    media_file_id: Optional[int] = None
    media_type: str = ""
    media_id: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    completed: bool = False
    id: Optional[int] = None


@dataclass
class Favorite:
    profile_id: int = 0
    media_type: str = ""
    media_id: int = 0
    created_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class WatchlistItem:
    profile_id: int = 0
    media_type: str = ""
    media_id: int = 0
    added_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class UserRating:
    profile_id: int = 0
    media_type: str = ""
    media_id: int = 0
    rating: float = 0.0
    rated_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class Tag:
    name: str = ""
    id: Optional[int] = None


@dataclass
class ExternalId:
    media_type: str = ""
    media_id: int = 0
    provider: str = ""
    value: str = ""
    id: Optional[int] = None


@dataclass
class Artwork:
    owner_type: str = ""
    owner_id: int = 0
    kind: str = ""  # ArtworkKind value
    source_url: str = ""
    local_path: str = ""
    width: int = 0
    height: int = 0
    downloaded_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class BrowserHistoryEntry:
    url: str = ""
    title: str = ""
    visited_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class Bookmark:
    title: str = ""
    url: str = ""
    folder: str = ""
    added_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class DownloadRecord:
    url: str = ""
    path: str = ""
    state: str = "running"  # running | completed | cancelled | failed
    bytes_total: int = 0
    bytes_received: int = 0
    mime_type: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class ServiceAccount:
    service_id: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[datetime] = None
    id: Optional[int] = None
