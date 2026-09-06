"""Service registry & manager: online services center.

Services are declarative definitions (data, not UI). Adding a service
means adding a ServiceDefinition to the registry — the sidebar/services
screen render whatever is registered. No hard-coded service buttons in UI
code.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.browser.engine import open_in_system_browser, webengine_available
from app.database.repositories import Repositories

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceDefinition:
    id: str
    name: str
    description: str = ""
    url: str = ""
    category: str = "media"  # media | messaging | music | streaming | selfhosted
    requires_drm: bool = False
    embedded_allowed: bool = True       # sensible to open in the embedded browser
    external_preferred: bool = False    # better in a real browser
    auth_strategy: str = "none"         # none | external | cookies | account
    icon_emoji: str = ""                # glyph used by tiles
    accent: str = "#e50914"
    configurable_url: bool = False      # user can set a custom server URL


@dataclass
class ServiceStatus:
    definition: ServiceDefinition
    embedded_available: bool
    external_available: bool
    external_browser: str
    configured_url: str
    notes: str = ""


# --- built-in service catalog ---------------------------------------------------
# The product catalog is exactly: YouTube, Telegram, Spotify, TV Time.
# (Netflix/Prime/Disney/Plex/Jellyfin definitions remain importable but are
# deliberately not registered.)
def _builtin_services() -> list[ServiceDefinition]:
    from app.services import spotify, telegram, tv_time, youtube

    return [
        youtube.DEFINITION,
        telegram.DEFINITION,
        spotify.DEFINITION,
        tv_time.DEFINITION,
    ]


class ServiceRegistry:
    """Registry of known services; custom services can be registered too."""

    def __init__(self, builtin: list[ServiceDefinition] | None = None) -> None:
        self._services: dict[str, ServiceDefinition] = {
            service.id: service for service in (builtin if builtin is not None else _builtin_services())
        }

    def register(self, definition: ServiceDefinition) -> None:
        self._services[definition.id] = definition

    def all(self) -> list[ServiceDefinition]:
        return sorted(self._services.values(), key=lambda s: (s.category, s.name))

    def get(self, service_id: str) -> ServiceDefinition | None:
        return self._services.get(service_id)


class ServiceManager:
    """Resolves service availability and opens services."""

    def __init__(self, registry: ServiceRegistry, repos: Repositories, preferred_browser: str = "auto") -> None:
        self.registry = registry
        self.repos = repos
        self.preferred_browser = preferred_browser

    def set_preferred_browser(self, key: str) -> None:
        self.preferred_browser = key

    def configured_url(self, definition: ServiceDefinition) -> str:
        config = self.repos.service_accounts.get_config(definition.id)
        return config.get("url") or definition.url

    def set_configured_url(self, service_id: str, url: str) -> None:
        config = self.repos.service_accounts.get_config(service_id)
        if url:
            config["url"] = url
        else:
            config.pop("url", None)
        self.repos.service_accounts.set_config(service_id, config)

    def statuses(self) -> list[ServiceStatus]:
        from app.browser.engine import detect_system_browsers

        embedded, embedded_reason = webengine_available()
        browsers = detect_system_browsers()
        external_names = ", ".join(b.name for b in browsers[:4]) or "none detected"
        out = []
        for definition in self.registry.all():
            external_ok = bool(browsers)
            notes = ""
            if definition.requires_drm:
                notes = (
                    "DRM-protected: uses your system browser (embedded WebEngine "
                    "cannot play DRM content)."
                )
            elif definition.external_preferred:
                notes = "Best experience in a full browser."
            if not embedded and definition.embedded_allowed:
                notes = (notes + " " if notes else "") + f"Embedded browser unavailable: {embedded_reason}"
            out.append(
                ServiceStatus(
                    definition=definition,
                    embedded_available=embedded and definition.embedded_allowed,
                    external_available=external_ok,
                    external_browser=external_names,
                    configured_url=self.configured_url(definition),
                    notes=notes.strip(),
                )
            )
        return out

    def open_external(self, definition: ServiceDefinition) -> tuple[bool, str]:
        url = self.configured_url(definition)
        preferred = "auto" if not definition.requires_drm else self.preferred_browser
        ok, info = open_in_system_browser(url, preferred)
        return ok, info

    def open_url(self, definition: ServiceDefinition) -> tuple[bool, str]:
        """Open wherever appropriate: returns (opened_embedded, url)."""
        if definition.embedded_allowed:
            return True, self.configured_url(definition)
        return False, self.configured_url(definition)
