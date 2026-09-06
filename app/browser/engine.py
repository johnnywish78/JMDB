"""Browser engines: embedded WebEngine + system browser detection.

System browsers are *discovered* (PATH, desktop entries, common install
locations, $BROWSER) — never hard-coded to one machine.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def webengine_available() -> tuple[bool, str]:
    """(available, reason)."""
    try:
        from PyQt6 import QtWebEngineWidgets  # noqa: F401

        return True, ""
    except Exception as exc:
        return False, f"PyQt6-WebEngine not available: {exc}"


@dataclass
class SystemBrowser:
    key: str
    name: str
    path: str
    drm_capable: bool = False


# Discovery order matters for the "prefer Chrome for DRM" flow.
_BROWSER_COMMANDS = [
    ("chrome", "Google Chrome", True),
    ("chromium", "Chromium", True),
    ("chromium-browser", "Chromium", True),
    ("microsoft-edge", "Microsoft Edge", True),
    ("firefox", "Firefox", False),
    ("epiphany", "GNOME Web", False),
    ("konqueror", "Konqueror", False),
    ("falkon", "Falkon", False),
]


def detect_system_browsers() -> list[SystemBrowser]:
    """Find installed browsers via PATH, common locations, and $BROWSER."""
    found: dict[str, SystemBrowser] = {}
    for key, name, drm in _BROWSER_COMMANDS:
        path = shutil.which(key)
        if path:
            found[key] = SystemBrowser(key=key, name=name, path=path, drm_capable=drm)
    # common install locations not always on PATH
    extra_dirs = [
        "/usr/bin", "/usr/local/bin", "/opt/google/chrome", "/snap/bin",
        os.path.expanduser("~/.local/bin"), os.path.expanduser("~/bin"),
    ]
    for key, name, drm in _BROWSER_COMMANDS:
        if key in found:
            continue
        for directory in extra_dirs:
            candidate = os.path.join(directory, key)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                found[key] = SystemBrowser(key=key, name=name, path=candidate, drm_capable=drm)
                break
    # desktop entries via xdg-settings, if available
    try:
        default = subprocess.run(
            ["xdg-settings", "get", "default-web-browser"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if default and default.endswith(".desktop"):
            desktop_name = default.replace("-stable.desktop", "").replace(".desktop", "")
            lookup = {
                "google-chrome": ("chrome", "Google Chrome", True),
                "chromium": ("chromium", "Chromium", True),
                "chromium-browser": ("chromium-browser", "Chromium", True),
                "microsoft-edge": ("microsoft-edge", "Microsoft Edge", True),
                "firefox": ("firefox", "Firefox", False),
                "firefox-esr": ("firefox", "Firefox ESR", False),
                "org.mozilla.firefox": ("firefox", "Firefox", False),
            }
            if desktop_name in lookup and lookup[desktop_name][0] not in found:
                key, name, drm = lookup[desktop_name]
                path = shutil.which(key) or shutil.which("xdg-open")
                if path:
                    found[key] = SystemBrowser(key=key, name=name, path=path, drm_capable=drm)
    except (OSError, subprocess.TimeoutExpired):
        pass
    # $BROWSER env (can be a colon-separated list)
    for entry in (os.environ.get("BROWSER") or "").split(":"):
        if not entry:
            continue
        path = shutil.which(entry) or (entry if os.path.isfile(entry) else "")
        if path and "generic" not in found:
            found["generic"] = SystemBrowser(key="generic", name=f"Browser ({entry})", path=path)
    # always offer xdg-open as the "system default" option
    xdg = shutil.which("xdg-open")
    if xdg:
        found["default"] = SystemBrowser(key="default", name="System default browser", path=xdg)
    order = {key: i for i, (key, _, _) in enumerate(_BROWSER_COMMANDS)}
    result = sorted(found.values(), key=lambda b: order.get(b.key, 99))
    return result


def pick_browser(preferred: str = "auto") -> SystemBrowser | None:
    browsers = detect_system_browsers()
    if preferred == "auto":
        # prefer a DRM-capable Chromium browser, then anything, then default
        for browser in browsers:
            if browser.key in ("chrome", "chromium", "chromium-browser"):
                return browser
        return browsers[0] if browsers else None
    for browser in browsers:
        if browser.key == preferred:
            return browser
    if preferred == "default":
        for browser in browsers:
            if browser.key == "default":
                return browser
    return browsers[0] if browsers else None


def open_in_system_browser(url: str, preferred: str = "auto") -> tuple[bool, str]:
    """Open URL externally. Returns (ok, browser_name_or_error)."""
    browser = pick_browser(preferred)
    if browser is None:
        return False, "no system browser detected"
    try:
        subprocess.Popen([browser.path, url])
        return True, browser.name
    except OSError as exc:
        logger.error("failed to open browser %s: %s", browser.path, exc)
        return False, str(exc)
