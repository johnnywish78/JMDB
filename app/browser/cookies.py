"""Cookie / persistent profile configuration for the embedded browser."""
from __future__ import annotations

import logging

from app.config.paths import Paths
from app.config.settings import SettingsService

logger = logging.getLogger(__name__)


def configure_profile(profile, settings: SettingsService) -> None:
    """Apply cookie persistence policy to a QWebEngineProfile.

    Cookies and session data stay in ~/.jmdb/browser/profile — outside the
    repository, never committed.
    """
    from PyQt6.QtWebEngineCore import QWebEngineProfile

    if settings.get("browser_allow_cookies"):
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
    else:
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )


def clear_browsing_data(paths: Paths, profile=None) -> None:
    """Remove cached cookies/sessions from disk."""
    if profile is not None:
        try:
            profile.clearAllVisitedLinks()
        except Exception:
            pass
    for sub in ("Cookies", "Sessions", "IndexedDB"):
        target = paths.browser_profile / sub
        if target.exists():
            for item in target.rglob("*"):
                try:
                    item.unlink()
                except OSError:
                    pass


def user_agent_mode(settings: SettingsService) -> str:
    """Only used to pick a legitimate UA string when the user opts in."""
    return "default"
