"""Domain dataclasses. Rows returned by repositories are plain dicts;
these dataclasses are used for *new* data entering the system (scanner,
metadata providers) and for playback payloads."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import MediaKind


@dataclass
class MediaItem:
    kind: MediaKind
    title: str
    original_title: str = ""
    year: int | None = None
    rating: float = 0.0
    overview: str = ""
    runtime_min: int = 0
    genres: list[str] = field(default_factory=list)
    file_path: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    imdb_id: str = ""
    tmdb_id: int | None = None
    added_at: int = 0
    id: int = 0


@dataclass
class EpisodeRef:
    show_id: int
    season: int
    number: int
    title: str = ""
    runtime_min: int = 0
    file_path: str | None = None
    id: int = 0


@dataclass
class PlayPosition:
    media_key: str
    position_s: int
    duration_s: int
    updated_at: int


@dataclass
class HistoryEntry:
    media_key: str
    media_title: str
    subtitle: str
    started_at: int
    finished_at: int


@dataclass
class DetectedMedia:
    """Output of the filename detector."""
    path: str
    kind: MediaKind
    title: str
    year: int | None = None
    season: int | None = None
    number: int | None = None


@dataclass
class PlaybackPayload:
    """Everything the player screen + playback service need."""
    media_key: str
    title: str
    subtitle: str
    file_path: str | None
    duration_s: int
    media_id: int | None = None
    episode_id: int | None = None
    show_id: int | None = None
    season: int | None = None
    number: int | None = None
