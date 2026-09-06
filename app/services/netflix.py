"""Netflix service — DRM streaming: external browser only.

Widevine DRM content cannot play inside a desktop-embedded WebEngine
without the proprietary components; JMDB is honest about this and opens
Netflix in the user's system browser (Chromium-based preferred).
"""
from __future__ import annotations

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="netflix",
    name="Netflix",
    description="Requires DRM: opens in your system browser",
    url="https://www.netflix.com",
    category="streaming",
    requires_drm=True,
    embedded_allowed=False,
    external_preferred=True,
    icon_emoji="N",
    accent="#e50914",
)
