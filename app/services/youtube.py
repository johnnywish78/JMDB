"""YouTube service: embedded + external, direct video/app links."""
from __future__ import annotations

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="youtube",
    name="YouTube",
    description="Videos, music, channels",
    url="https://www.youtube.com",
    category="media",
    embedded_allowed=True,
    icon_emoji="▶",
    accent="#ff0000",
)


def app_url() -> str:
    return "https://www.youtube.com"


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
