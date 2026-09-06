"""TV Time service: opens the tracker's web app in the Browser Hub.

TV Time exposes no public API for third-party clients, so JMDB integrates
it honestly: a persistent web-app tab (login state survives restarts via
the Electron session), nothing faked behind it.
"""
from __future__ import annotations

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="tv_time",
    name="TV Time",
    description="Track shows you watch",
    url="https://www.tvtime.com",
    category="media",
    embedded_allowed=True,
    icon_emoji="📅",
    accent="#2d9cdb",
)
