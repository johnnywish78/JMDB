"""Telegram service: web client + installed-client deep link."""
from __future__ import annotations

import shutil

from app.services.service_manager import ServiceDefinition

DEFINITION = ServiceDefinition(
    id="telegram",
    name="Telegram",
    description="Messaging (Telegram Web)",
    url="https://web.telegram.org",
    category="messaging",
    embedded_allowed=True,
    icon_emoji="✈",
    accent="#2aabee",
)


def web_url() -> str:
    return "https://web.telegram.org"


def has_desktop_client() -> bool:
    return any(shutil.which(cmd) for cmd in ("telegram-desktop", "telegram"))
