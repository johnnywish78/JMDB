"""WebEngine permission policy (deny by default, user-grantable)."""
from __future__ import annotations

from app.config.settings import SettingsService


class PermissionPolicy:
    """Decides permission requests for the embedded browser.

    Defaults are privacy-preserving: notifications, geolocation, and
    audio/video capture are denied; fullscreen is allowed (needed for
    video playback).
    """

    def __init__(self, settings: SettingsService) -> None:
        self.settings = settings

    def allow(self, feature) -> bool:
        from PyQt6.QtWebEngineCore import QWebEnginePage

        allowed = {
            QWebEnginePage.Feature.FullScreen: True,
            QWebEnginePage.Feature.Notifications: False,
            QWebEnginePage.Feature.Geolocation: False,
            QWebEnginePage.Feature.MediaAudioCapture: False,
            QWebEnginePage.Feature.MediaVideoCapture: False,
            QWebEnginePage.Feature.MediaAudioVideoCapture: False,
            QWebEnginePage.Feature.MouseLock: True,
            QWebEnginePage.Feature.DesktopVideoCapture: False,
            QWebEnginePage.Feature.DesktopAudioVideoCapture: False,
            QWebEnginePage.Feature.Notifications: False,
        }
        return allowed.get(feature, False)

    def register(self, page) -> None:
        """Hook the policy into a QWebEnginePage via its profile."""
        try:
            profile = page.profile()
            profile.setNotificationPresenter(lambda _n: None)
        except Exception:
            pass
