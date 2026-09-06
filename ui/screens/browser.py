"""Embedded browser screen (WebEngine) with honest fallback."""
from __future__ import annotations

import logging

from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.browser.engine import open_in_system_browser, webengine_available
from ui.app.context import icon
from ui.screens.base import Screen

logger = logging.getLogger(__name__)

HOME_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>JMDB Browser</title>
<style>
 body{font-family:sans-serif;background:#14171e;color:#e6e9f0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
 .box{max-width:520px;text-align:center}h1{color:#ffb648}a{color:#7ab2ff;text-decoration:none;margin:0 10px}
 p{color:#8b94a7;line-height:1.6}
</style></head><body><div class="box">
<h1>JMDB Browser</h1>
<p>Type an address above, or use the Services screen to open your streaming and media sites.</p>
<p><a href="https://www.youtube.com">YouTube</a> <a href="https://en.wikipedia.org">Wikipedia</a> <a href="https://www.themoviedb.org">TMDB</a></p>
</div></body></html>"""


class BrowserTabWidget(QWidget):
    url_changed = pyqtSignal(str)

    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.back_button = self._nav_button("back", "Back", self._back)
        self.forward_button = self._nav_button("skip_next", "Forward", self._forward)
        self.reload_button = self._nav_button("refresh", "Reload", self._reload)
        self.stop_button = self._nav_button("close", "Stop", self._stop)
        self.home_button = self._nav_button("home", "Home", self._home)
        self.url_entry = QLineEdit()
        self.url_entry.setObjectName("SearchEntry")
        self.url_entry.returnPressed.connect(self._go)
        toolbar.addWidget(self.back_button)
        toolbar.addWidget(self.forward_button)
        toolbar.addWidget(self.reload_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addWidget(self.home_button)
        toolbar.addWidget(self.url_entry, 1)
        self.external_button = self._nav_button("globe", "Open in system browser", self._external)
        toolbar.addWidget(self.external_button)
        layout.addLayout(toolbar)

        # find bar
        self.find_bar = QWidget()
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(0, 0, 0, 0)
        self.find_entry = QLineEdit()
        self.find_entry.setPlaceholderText("Find in page…")
        self.find_entry.textChanged.connect(self._find_changed)
        self.find_next = QPushButton("Next")
        self.find_next.clicked.connect(lambda: self._find(True))
        self.find_prev = QPushButton("Prev")
        self.find_prev.clicked.connect(lambda: self._find(False))
        self.find_close = QPushButton("✕")
        self.find_close.clicked.connect(self._hide_find)
        find_layout.addWidget(QLabel("Find:"))
        find_layout.addWidget(self.find_entry, 1)
        find_layout.addWidget(self.find_prev)
        find_layout.addWidget(self.find_next)
        find_layout.addWidget(self.find_close)
        self.find_bar.hide()
        layout.addWidget(self.find_bar)

        from app.browser.tabs import BrowserTab

        self.tab = BrowserTab(
            context.services.paths,
            context.services.settings,
            context.services.browser_history,
            context.services.downloads_manager,
            self,
        )
        self.tab.url_changed.connect(self._on_url)
        self.tab.title_changed.connect(lambda title: self.setWindowTitle(title))
        self.tab_view = self.tab
        layout.addWidget(self.tab, 1)

        self._load_home()

    def _nav_button(self, icon_name: str, tooltip: str, handler) -> QPushButton:
        button = QPushButton()
        button.setObjectName("FlatIconButton")
        button.setIcon(icon(icon_name))
        button.setToolTip(tooltip)
        button.clicked.connect(handler)
        return button

    # -- actions -------------------------------------------------------------
    def _load_home(self) -> None:
        import base64

        data = base64.b64encode(HOME_PAGE.encode()).decode()
        self.tab.load(f"data:text/html;base64,{data}")

    def _go(self) -> None:
        url = self.url_entry.text().strip()
        if url:
            self.tab.load(url)

    def _back(self) -> None: self.tab.back()
    def _forward(self) -> None: self.tab.forward()
    def _reload(self) -> None: self.tab.reload()
    def _stop(self) -> None: self.tab.stop()
    def _home(self) -> None: self._load_home()

    def _external(self) -> None:
        url = self.tab.current_url
        if url.startswith(("http://", "https://")):
            ok, info = open_in_system_browser(url, "auto")
            if not ok:
                self.context.toast("No system browser detected", "warning")

    def show_find(self) -> None:
        self.find_bar.show()
        self.find_entry.setFocus()

    def _hide_find(self) -> None:
        self.tab.clear_find()
        self.find_bar.hide()

    def _find_changed(self, text: str) -> None:
        if text:
            self.tab.find(text, forward=True)

    def _find(self, forward: bool) -> None:
        if self.find_entry.text():
            self.tab.find(self.find_entry.text(), forward=forward)

    def zoom_in(self) -> None: self.tab.zoom_in()
    def zoom_out(self) -> None: self.tab.zoom_out()
    def zoom_reset(self) -> None: self.tab.zoom_reset()

    def _on_url(self, url: str) -> None:
        self.url_entry.setText(url)
        self.url_changed.emit(url)

    def load_url(self, url: str) -> None:
        self.tab.load(url)


class BrowserScreen(Screen):
    title = "Browser"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Browser")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)

        self.available, self.reason = webengine_available()
        if self.available:
            self._build_browser()
        else:
            self._build_fallback()

    def _build_browser(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.root.addWidget(self.tabs, 1)
        self.new_tab_button = QPushButton("＋ New tab")
        self.new_tab_button.clicked.connect(self._new_tab)
        self.root.addWidget(self.new_tab_button)
        self._new_tab()

    def _new_tab(self, url: str = "") -> None:
        widget = BrowserTabWidget(self.context)
        index = self.tabs.addTab(widget, "New tab")
        widget.tab.title_changed.connect(
            lambda title, idx=index: self.tabs.setTabText(idx, title[:22] or "New tab")
        )
        self.tabs.setCurrentIndex(index)
        if url:
            widget.load_url(url)

    def _close_tab(self, index: int) -> None:
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)

    def enter(self, url: str = "", **params) -> None:
        if url and self.available:
            # navigate in a fresh tab (or current if still on home)
            self._new_tab(url)

    def refresh(self) -> None:
        pass  # live widget, nothing to reload

    def _build_fallback(self) -> None:
        from ui.components.states import EmptyState

        fallback = EmptyState(
            "Embedded browser unavailable",
            f"{self.reason}\n\nInstall it with:\n    pip install PyQt6-WebEngine\n\n"
            "Meanwhile, use 'Open in system browser' from the Services screen.",
            "Open Services",
            glyph="🌐",
        )
        fallback.action.connect(lambda: self.context.router.navigate("services"))
        self.root.addWidget(fallback, 1)
