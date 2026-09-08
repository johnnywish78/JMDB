"""Embedded JMDB browser powered by QtWebEngine. Full navigation bar with
back / forward / reload / stop / home, address bar, loading indicator, and
external-browser fallback for DRM-restricted sites."""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("jmdb.browser")

# Qt is imported lazily so the pure helpers (URL normalization, engine probe)
# remain importable headless (tests, diagnostics, non-Qt backends).
try:  # pragma: no cover - depends on environment
    from PyQt6.QtCore import QUrl, QTimer  # noqa: F401
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    _QT_OK = True
    _QT_ERR = ""
except Exception as _exc:  # pragma: no cover - headless
    QUrl = QTimer = QHBoxLayout = QLabel = QLineEdit = QPushButton = QVBoxLayout = QWidget = None  # type: ignore
    _QT_OK = False
    _QT_ERR = str(_exc)

# --------------------------------------------------------------------------- init
_WEBENGINE_OK: bool | None = None
_WEBENGINE_ERR: str = ""


def _probe_webengine() -> tuple[bool, str]:
    """Return (available, reason)."""
    global _WEBENGINE_OK, _WEBENGINE_ERR
    if _WEBENGINE_OK is not None:
        return _WEBENGINE_OK, _WEBENGINE_ERR
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        # Try instantiating — may fail on some headless / X11 setups
        app = None
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
        except Exception:
            pass
        if app is None:
            # Not in a Qt app yet; we can only confirm the import works
            _WEBENGINE_OK = True
            _WEBENGINE_ERR = ""
        else:
            _WEBENGINE_OK = True
            _WEBENGINE_ERR = ""
    except Exception as exc:  # pragma: no cover - env-dependent
        _WEBENGINE_OK = False
        _WEBENGINE_ERR = f"WebEngine unavailable: {exc}"
    return _WEBENGINE_OK, _WEBENGINE_ERR


DEFAULT_URL = "https://duckduckgo.com"


def _normalize(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return DEFAULT_URL
    if "://" not in url:
        url = "https://" + url
    return url


_Base = QWidget if _QT_OK else object


class BrowserWidget(_Base):
    """Full-featured embedded browser. Falls back to external browser on error."""

    def __init__(self, bookmarks, parent=None):
        if not _QT_OK:
            raise RuntimeError(f"JMDB browser widget requires PyQt6: {_QT_ERR}")
        super().__init__(parent)
        self.bookmarks = bookmarks
        self._web = None
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── navigation toolbar ───────────────────────────────────────────────
        nav = QHBoxLayout()
        nav.setContentsMargins(6, 4, 6, 4)
        nav.setSpacing(4)

        self.btn_back = QPushButton("◀")
        self.btn_back.setFixedWidth(32)
        self.btn_back.setToolTip("Back")
        self.btn_forward = QPushButton("▶")
        self.btn_forward.setFixedWidth(32)
        self.btn_forward.setToolTip("Forward")
        self.btn_reload = QPushButton("↺")
        self.btn_reload.setFixedWidth(32)
        self.btn_reload.setToolTip("Reload")
        self.btn_stop = QPushButton("✕")
        self.btn_stop.setFixedWidth(32)
        self.btn_stop.setToolTip("Stop")
        self.btn_home = QPushButton("⌂")
        self.btn_home.setFixedWidth(32)
        self.btn_home.setToolTip("Home")
        self.btn_external = QPushButton("↗ External")
        self.btn_external.setToolTip("Open in system browser")
        self.btn_bookmark = QPushButton("☆ Bookmark")
        self.btn_bookmark.setToolTip("Bookmark current page")

        for b in (self.btn_back, self.btn_forward, self.btn_reload,
                  self.btn_stop, self.btn_home, self.btn_external):
            b.setFixedHeight(28)
        self.btn_bookmark.setFixedHeight(28)

        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_forward)
        nav.addWidget(self.btn_reload)
        nav.addWidget(self.btn_stop)
        nav.addWidget(self.btn_home)
        nav.addWidget(QLabel("  "), 0)

        self.url_edit = QLineEdit(DEFAULT_URL)
        self.url_edit.setObjectName("SearchEdit")
        self.url_edit.setPlaceholderText("Search or enter URL …")
        nav.addWidget(self.url_edit, 1)

        self.btn_go = QPushButton("Go")
        self.btn_go.setFixedHeight(28)
        nav.addWidget(self.btn_go)
        nav.addWidget(self.btn_bookmark)
        nav.addWidget(self.btn_external)
        root.addLayout(nav)

        # ── web view or fallback ─────────────────────────────────────────────
        ok, err = _probe_webengine()
        self._web_available = ok
        if ok:
            self.web = self._make_webview()
            self.web.load(QUrl(DEFAULT_URL))
            root.addWidget(self.web, 1)
            self.web.urlChanged.connect(self._on_url_changed)
            self.web.loadStarted.connect(self._on_load_started)
            self.web.loadFinished.connect(self._on_load_finished)
            self.web.loadProgress.connect(self._on_load_progress)
        else:
            self.web = None
            note = QLabel(
                f"Embedded browser unavailable.<br><small>{err}</small><br><br>"
                "Use the ↗ External button to open pages in your system browser."
            )
            note.setStyleSheet("padding:40px;color:#8b93a7;font-size:13px")
            note.setWordWrap(True)
            root.addWidget(note, 1)

        # ── loading progress bar ─────────────────────────────────────────────
        self.progress_bar = QLabel("")
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        # ── wiring ───────────────────────────────────────────────────────────
        self.btn_go.clicked.connect(lambda: self.open_url(self.url_edit.text()))
        self.url_edit.returnPressed.connect(
            lambda: self.open_url(self.url_edit.text()))
        self.url_edit.editingFinished.connect(
            lambda: self.open_url(self.url_edit.text()))
        self.btn_back.clicked.connect(lambda: self._nav_action("back"))
        self.btn_forward.clicked.connect(lambda: self._nav_action("forward"))
        self.btn_reload.clicked.connect(self._reload)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_home.clicked.connect(lambda: self.open_url(DEFAULT_URL))
        self.btn_external.clicked.connect(self._open_external)
        self.btn_bookmark.clicked.connect(self._bookmark_current)

    # ------------------------------------------------------------------ webview
    def _make_webview(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        view = QWebEngineView()
        view.setContextMenuPolicy(
            Qt.ContextMenuPolicy.DefaultContextMenu)
        return view

    # ------------------------------------------------------------------ actions
    def open_url(self, url: str) -> None:
        url = _normalize(url)
        self.url_edit.setText(url)
        if self.web is not None:
            self.web.load(QUrl(url))
        else:
            self._open_external(url)

    def _nav_action(self, action: str) -> None:
        if self.web is None:
            return
        if action == "back" and self.web.history().canGoBack():
            self.web.history().back()
        elif action == "forward" and self.web.history().canGoForward():
            self.web.history().forward()

    def _reload(self) -> None:
        if self.web is not None:
            self.web.reload()

    def _stop(self) -> None:
        if self.web is not None:
            self.web.page().stop()
            self.progress_bar.hide()
            self._loading = False

    def _open_external(self, url: str | None = None) -> None:
        from app.services.service_manager import ServiceManager
        ServiceManager.open_external(_normalize(url or self.url_edit.text()))

    def _bookmark_current(self) -> None:
        url = self.url_edit.text() or DEFAULT_URL
        name = QUrl(_normalize(url)).host().remove("www.") or url
        self.bookmarks.add(name, url)

    # ------------------------------------------------------------------ signals
    def _on_url_changed(self, url: QUrl) -> None:
        text = url.toString()
        if text != self.url_edit.text():
            self.url_edit.setText(text)

    def _on_load_started(self) -> None:
        self._loading = True
        self.progress_bar.show()
        self.progress_bar.setText("")
        self.btn_stop.show()

    def _on_load_finished(self, ok: bool) -> None:
        self._loading = False
        self.progress_bar.hide()
        self.btn_stop.hide()
        if not ok:
            self._on_error("Page load failed")

    def _on_load_progress(self, pct: int) -> None:
        if self._loading:
            self.progress_bar.setText(f"{pct}%")

    def _on_error(self, msg: str) -> None:
        if self.web is not None and hasattr(self.web, "title"):
            self.url_edit.setText(f"error: {msg}")


def engine_available() -> bool:
    ok, _ = _probe_webengine()
    return ok
