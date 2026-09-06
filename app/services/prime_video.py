"""Prime Video service — DRM streaming: external browser only."""
from __future__ import annotations

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="prime_video",
    name="Prime Video",
    description="Requires DRM: opens in your system browser",
    url="https://www.primevideo.com",
    category="streaming",
    requires_drm=True,
    embedded_allowed=False,
    external_preferred=True,
    icon_emoji="P",
    accent="#00a8e1",
)
