"""Jellyfin service: user-configured server URL, embedded or external."""
from __future__ import annotations

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="jellyfin",
    name="Jellyfin",
    description="Your Jellyfin server (configure URL)",
    url="http://localhost:8096",
    category="selfhosted",
    embedded_allowed=True,
    configurable_url=True,
    auth_strategy="account",
    icon_emoji="J",
    accent="#aa5cc3",
)
