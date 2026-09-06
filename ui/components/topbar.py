"""Top bar: search, quick actions."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ui.app.context import icon


class Topbar(QWidget):
    search_requested = pyqtSignal(str)
    theme_toggled = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Topbar")
        self.setFixedHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)

        self.search_entry = QLineEdit()
        self.search_entry.setObjectName("SearchEntry")
        self.search_entry.setPlaceholderText("Search movies, shows, people, music…  (Ctrl+K)")
        self.search_entry.setClearButtonEnabled(True)
        self.search_entry.setMinimumWidth(420)
        layout.addWidget(self.search_entry, 1)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("FlatIconButton")
        self.theme_button.setIcon(icon("moon"))
        self.theme_button.setToolTip("Switch light/dark theme")
        self.theme_button.clicked.connect(self.theme_toggled.emit)
        layout.addWidget(self.theme_button)

        # debounced instant search
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(280)
        self._debounce.timeout.connect(self._emit_search)
        self.search_entry.textChanged.connect(lambda _t: self._debounce.start())
        self.search_entry.returnPressed.connect(self._emit_search)

    def _emit_search(self) -> None:
        text = self.search_entry.text().strip()
        if text:
            self.search_requested.emit(text)

    def set_search_text(self, text: str) -> None:
        self.search_entry.setText(text)

    def set_theme_icon(self, theme: str) -> None:
        self.theme_button.setIcon(icon("sun" if theme == "dark" else "moon"))
