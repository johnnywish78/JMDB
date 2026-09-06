"""Shared enumerations."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Enum that serializes to its value as a plain string."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class MediaKind(StrEnum):
    """What a file on disk is."""

    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    IMAGE = "image"
    OTHER = "other"


class MediaType(StrEnum):
    """Addressable library entities (used for polymorphic relations)."""

    MOVIE = "movie"
    TV_SHOW = "tv_show"
    SEASON = "season"
    EPISODE = "episode"
    PERSON = "person"
    ARTIST = "artist"
    ALBUM = "album"
    TRACK = "track"
    COLLECTION = "collection"  # user collection


class LinkType(StrEnum):
    """media_file_links.media_item_type values."""

    MOVIE = "movie"
    EPISODE = "episode"
    TRACK = "track"


class CreditRole(StrEnum):
    ACTOR = "actor"
    DIRECTOR = "director"
    WRITER = "writer"
    PRODUCER = "producer"
    CREW = "crew"
    GUEST_STAR = "guest_star"


class ArtworkKind(StrEnum):
    POSTER = "poster"
    BACKDROP = "backdrop"
    LOGO = "logo"
    PROFILE = "profile"
    STILL = "still"
    SEASON_POSTER = "season_poster"
    ALBUM_COVER = "album_cover"
    ARTIST_BANNER = "artist_banner"


class OwnerType(StrEnum):
    """artwork.owner_type values."""

    MOVIE = "movie"
    TV_SHOW = "tv_show"
    SEASON = "season"
    EPISODE = "episode"
    PERSON = "person"
    ARTIST = "artist"
    ALBUM = "album"


class ScanStatus(StrEnum):
    NEVER = "never"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlaybackBackendId(StrEnum):
    AUTO = "auto"
    VLC = "vlc"
    MPV = "mpv"
    QT = "qt"
    EXTERNAL = "external"


class PlayerState(StrEnum):
    IDLE = "idle"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    FINISHED = "finished"
    ERROR = "error"
