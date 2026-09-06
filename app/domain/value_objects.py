"""Value objects shared across layers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PlayableItem:
    """Something the player can play: a concrete file bound to a library item."""

    media_type: str  # movie | episode | track
    media_id: int
    media_file_id: int
    path: str
    title: str
    subtitle: str = ""
    duration_seconds: float = 0.0
    artwork_path: str = ""

    def display_title(self) -> str:
        if self.subtitle:
            return f"{self.title} — {self.subtitle}"
        return self.title


@dataclass(frozen=True)
class ExternalIds:
    """Provider IDs attached to a library entity."""

    tmdb: Optional[str] = None
    imdb: Optional[str] = None
    omdb: Optional[str] = None
    tvmaze: Optional[str] = None
    tvtime: Optional[str] = None
    itunes: Optional[str] = None
    musicbrainz: Optional[str] = None
    lastfm: Optional[str] = None
    theaudiodb: Optional[str] = None
    fanarttv: Optional[str] = None

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass(frozen=True)
class TrackSelection:
    """A selectable audio/subtitle track inside a media file."""

    index: int
    kind: str  # audio | subtitle
    language: str = ""
    title: str = ""
    codec: str = ""
    is_default: bool = False

    def label(self) -> str:
        base = self.title or self.language or f"Track {self.index}"
        if self.language and self.title and self.language.lower() not in self.title.lower():
            base = f"{base} ({self.language})"
        return base
