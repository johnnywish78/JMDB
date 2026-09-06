"""Plex service: user-configured server URL, embedded or external."""
from __future__ import annotations

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="plex",
    name="Plex",
    description="Your Plex server (configure URL)",
    url="https://app.plex.tv",
    category="selfhosted",
    embedded_allowed=True,
    configurable_url=True,
    auth_strategy="account",
    icon_emoji="Ø",
    accent="#e5a00d",
)
