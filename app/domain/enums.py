"""Enumerations shared across layers."""
from __future__ import annotations

from enum import Enum


class MediaKind(str, Enum):
    MOVIE = "movie"
    SHOW = "show"
    EPISODE = "episode"
    MUSIC = "music"


class BackendType(str, Enum):
    AUTO = "auto"
    MPV = "mpv"
    VLC = "vlc"
    QT = "qt"
    EXTERNAL = "external"


class WatchStatus(str, Enum):
    NONE = "none"
    IN_PROGRESS = "in_progress"
    WATCHED = "watched"


class PersonRole(str, Enum):
    ACTOR = "actor"
    DIRECTOR = "director"
    CREATOR = "creator"


MEDIA_KEY_PREFIX_MOVIE = "m:"
MEDIA_KEY_PREFIX_EPISODE = "e:"


def media_key_movie(media_id: int) -> str:
    return f"{MEDIA_KEY_PREFIX_MOVIE}{media_id}"


def media_key_episode(episode_id: int) -> str:
    return f"{MEDIA_KEY_PREFIX_EPISODE}{episode_id}"


def parse_media_key(key: str) -> tuple[str, int] | None:
    for prefix in (MEDIA_KEY_PREFIX_MOVIE, MEDIA_KEY_PREFIX_EPISODE):
        if key.startswith(prefix):
            try:
                return prefix.rstrip(":"), int(key[len(prefix):])
            except ValueError:
                return None
    return None
