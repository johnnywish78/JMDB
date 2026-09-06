"""Spotify service: web player + installed-client deep link."""
from __future__ import annotations

import shutil

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="spotify",
    name="Spotify",
    description="Music streaming (Spotify Web Player)",
    url="https://open.spotify.com",
    category="music",
    embedded_allowed=True,
    external_preferred=True,
    icon_emoji="♫",
    accent="#1db954",
)


def web_url() -> str:
    return "https://open.spotify.com"


def has_desktop_client() -> bool:
    return bool(shutil.which("spotify"))
