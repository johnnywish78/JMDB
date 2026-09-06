"""Search bar with suggestions."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QCompleter,
    QLineEdit,
    QWidget,
)

from ui.app.context import icon


class SearchBar(QWidget):
    """A standalone search entry (used on the Search screen)."""

    query_changed = pyqtSignal(str)
    submitted = pyqtSignal(str)

    def __init__(self, placeholder: str = "Search your library…", parent=None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.entry = QLineEdit()
        self.entry.setObjectName("SearchEntry")
        self.entry.setPlaceholderText(placeholder)
        self.entry.setClearButtonEnabled(True)
        layout.addWidget(self.entry)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(lambda: self.query_changed.emit(self.entry.text().strip()))
        self.entry.textChanged.connect(lambda _t: self._debounce.start())
        self.entry.returnPressed.connect(lambda: self.submitted.emit(self.entry.text().strip()))

    def set_suggestions(self, items: list[str]) -> None:
        completer = QCompleter(items, self.entry)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.entry.setCompleter(completer)

    def text(self) -> str:
        return self.entry.text().strip()

    def set_text(self, text: str) -> None:
        self.entry.setText(text)
