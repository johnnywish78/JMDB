"""Sidebar navigation. Every entry must map to a real route."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.app.context import icon

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    ("home", "Home", "home"),
    ("movies", "Movies", "movies"),
    ("tv", "TV Shows", "tv"),
    ("music", "Music", "music"),
    ("people", "People", "person"),
    ("collections", "Collections", "collection"),
    ("favorites", "Favorites", "heart"),
    ("watchlist", "Watchlist", "bookmark"),
    ("history", "History", "history"),
    ("search", "Search", "search"),
    ("recommendations", "Recommendations", "star"),
    ("statistics", "Statistics", "chart"),
    ("browser", "Browser", "globe"),
    ("services", "Services", "services"),
    ("settings", "Settings", "settings"),
]


class Sidebar(QWidget):
    navigate_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(212)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 14)
        layout.setSpacing(1)

        logo = QLabel("JMDB")
        logo.setObjectName("SidebarLogo")
        tagline = QLabel("Johnny Media Database")
        tagline.setObjectName("SidebarTagline")
        layout.addWidget(logo)
        layout.addWidget(tagline)
        layout.addSpacing(14)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for route, label, icon_name in NAV_ITEMS:
            button = QPushButton(f"  {label}")
            button.setIcon(icon(icon_name))
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"Go to {label}")
            button.clicked.connect(lambda _=False, r=route: self.navigate_requested.emit(r))
            self._group.addButton(button)
            layout.addWidget(button)
            self._buttons[route] = button
        layout.addStretch(1)

    def routes(self) -> list[str]:
        return [route for route, _label, _icon in NAV_ITEMS]

    def set_active(self, route: str) -> None:
        button = self._buttons.get(route)
        if button is not None:
            button.setChecked(True)
