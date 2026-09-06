"""TV Time — honest integration boundary.

TV Time (formerly TVShow Time) has **no public API** for third-party
metadata or watch-tracking; access requires an undocumented private app API
which would break terms of service. JMDB therefore:

* does NOT fake TV Time data,
* registers the provider as unavailable with a clear explanation,
* offers a service entry that opens the official TV Time website in the
  browser so users can track shows there,
* and stores ``tvtime`` external IDs if any future legitimate API appears.

This module is the documented boundary; see docs/metadata.md.
"""
from __future__ import annotations

from app.metadata.providers.base import MetadataProvider, ProviderUnavailable

TVTIME_URL = "https://www.tvtime.com"


class TvTimeProvider(MetadataProvider):
    id = "tvtime"
    display_name = "TV Time"
    requires_key = False
    capabilities = set()  # no metadata capability: no public API

    def is_configured(self) -> bool:
        return False  # honestly unavailable: no public API exists

    def health(self) -> dict:
        health = super().health()
        health["available"] = False
        health["last_error"] = "No public API — website link only (by design)"
        return health

    def search_show(self, title: str) -> list:
        raise ProviderUnavailable(
            "TV Time does not offer a public API. "
            "Use the Services screen to open tvtime.com in a browser."
        )

    def website_url(self) -> str:
        return TVTIME_URL
