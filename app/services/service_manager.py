"""External service registry + launch policy. JMDB stores NO third-party creds;
services open either in the embedded browser widget or the OS browser."""
from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import Settings


@dataclass(frozen=True)
class ServiceInfo:
    key: str
    name: str
    url: str
    color: str          # brand accent for the tile
    note: str = ""
    logo: str = ""      # local SVG/PNG path (empty = use icon)


def final_services(settings: Settings) -> list[ServiceInfo]:
    """The four supported JMDB services."""
    return [
        ServiceInfo(
            "youtube", "YouTube",
            "https://www.youtube.com",
            "#ff0000",
            "trailers, reviews & clips",
        ),
        ServiceInfo(
            "telegram", "Telegram",
            "https://web.telegram.org",
            "#2aabee",
            "channels & bot links",
        ),
        ServiceInfo(
            "spotify", "Spotify",
            "https://open.spotify.com",
            "#1db954",
            "soundtracks & playlists",
        ),
        ServiceInfo(
            "tvtime", "TV Time",
            "https://www.tvtime.com",
            "#f5a623",
            "episode tracking & reminders",
        ),
    ]


class ServiceManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def services(self) -> list[ServiceInfo]:
        return final_services(self.settings)

    def get(self, key: str) -> ServiceInfo | None:
        for s in self.services():
            if s.key == key:
                return s
        return None

    @staticmethod
    def open_external(url: str) -> bool:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        return QDesktopServices.openUrl(QUrl(url))
