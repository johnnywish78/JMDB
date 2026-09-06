"""Embedded browser tabs (WebEngine)."""
from __future__ import annotations

import logging
import weakref

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from app.browser.cookies import configure_profile
from app.browser.downloads import DownloadsManager
from app.browser.history import BrowserHistory
from app.browser.permissions import PermissionPolicy
from app.config.paths import Paths
from app.config.settings import SettingsService

logger = logging.getLogger(__name__)

# One shared profile per QApplication: all tabs share cookies/sessions
# (like a real browser). QWebEngineProfile names must be unique, and
# multiple profiles must not share a persistent storage path — hence a
# singleton instead of one profile per tab.
_shared_profiles: "weakref.WeakKeyDictionary[QApplication, QWebEngineProfile]" = (
    weakref.WeakKeyDictionary()
)


def shared_profile(paths: Paths, settings: SettingsService, downloads: DownloadsManager):
    """Return the app-wide browser profile, creating it on first use."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    profile = _shared_profiles.get(app)
    if profile is None:
        profile = QWebEngineProfile("jmdb-profile", app)
        profile.setPersistentStoragePath(str(paths.browser_profile))
        configure_profile(profile, settings)
        profile.downloadRequested.connect(downloads.handle_download)
        _shared_profiles[app] = profile
    return profile


class BrowserTab(QWidget):
    """One browser tab: a WebEngine view with metadata recording."""

    title_changed = pyqtSignal(str)
    url_changed = pyqtSignal(str)
    icon_changed = pyqtSignal(object)
    load_progress = pyqtSignal(int)

    def __init__(
        self,
        paths: Paths,
        settings: SettingsService,
        history: BrowserHistory,
        downloads: DownloadsManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.history = history

        self.profile = shared_profile(paths, settings, downloads)
        self.page = QWebEnginePage(self.profile, self)
        self.view = QWebEngineView(self)
        self.view.setPage(self.page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self.view.loadProgress.connect(self.load_progress)
        self.view.titleChanged.connect(self._on_title)
        self.view.urlChanged.connect(self._on_url)
        # signal-to-signal connect can fail on signature mismatch depending
        # on binding import order; a lambda slot always works
        self.view.iconChanged.connect(lambda icon: self.icon_changed.emit(icon))
        self.page.loadFinished.connect(self._on_loaded)
        self._current_title = ""

    # -- events -------------------------------------------------------------
    def _on_title(self, title: str) -> None:
        self._current_title = title
        self.title_changed.emit(title)

    def _on_url(self, url: QUrl) -> None:
        self.url_changed.emit(url.toString())

    def _on_loaded(self, ok: bool) -> None:
        if not ok:
            return
        url = self.view.url().toString()
        if url.startswith(("data:", "jmdb:", "about:")):
            return
        self.history.add(url, self._current_title)

    # -- navigation ------------------------------------------------------------
    def load(self, url: str) -> None:
        if url.startswith(("http://", "https://", "file://", "data:", "about:", "jmdb:")):
            target = QUrl(url)
        elif "." in url and " " not in url:
            target = QUrl(f"https://{url}")
        else:
            target = QUrl.fromUserInput(url)
        self.view.load(target)

    def back(self) -> None:
        self.view.back()

    def forward(self) -> None:
        self.view.forward()

    def reload(self) -> None:
        self.view.reload()

    def stop(self) -> None:
        self.view.stop()

    def find(self, text: str, forward: bool = True) -> None:
        from PyQt6.QtWebEngineCore import QWebEnginePage

        flags = QWebEnginePage.FindFlag(0)
        if not forward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        self.page.findText(text, flags)

    def clear_find(self) -> None:
        self.page.findText("")

    def zoom_in(self) -> None:
        self.view.setZoomFactor(min(3.0, self.view.zoomFactor() + 0.1))

    def zoom_out(self) -> None:
        self.view.setZoomFactor(max(0.3, self.view.zoomFactor() - 0.1))

    def zoom_reset(self) -> None:
        self.view.setZoomFactor(1.0)

    @property
    def can_go_back(self) -> bool:
        return self.view.history().canGoBack()

    @property
    def can_go_forward(self) -> bool:
        return self.view.history().canGoForward()

    @property
    def current_url(self) -> str:
        return self.view.url().toString()

    @property
    def current_title(self) -> str:
        return self._current_title or self.view.title() or self.current_url
