"""Disney+ service — DRM streaming: external browser only."""
from __future__ import annotations

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="disney_plus",
    name="Disney+",
    description="Requires DRM: opens in your system browser",
    url="https://www.disneyplus.com",
    category="streaming",
    requires_drm=True,
    embedded_allowed=False,
    external_preferred=True,
    icon_emoji="D",
    accent="#113ccf",
)
