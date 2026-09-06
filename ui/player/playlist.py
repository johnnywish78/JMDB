"""Player playlist panel."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ui.player.controls import format_time


class PlaylistPanel(QWidget):
    item_activated = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self.setFixedWidth(280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        from PyQt6.QtWidgets import QLabel

        header = QLabel("Playlist")
        header.setObjectName("SectionHeader")
        layout.addWidget(header)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(
            lambda item: self.item_activated.emit(self.list.row(item))
        )
        layout.addWidget(self.list, 1)

    def set_items(self, items: list, current_index: int = 0) -> None:
        self.list.clear()
        for index, item in enumerate(items):
            duration = getattr(item, "duration_seconds", 0) or 0
            text = f"{index + 1}. {item.title}"
            if getattr(item, "subtitle", ""):
                text += f" — {item.subtitle}"
            if duration:
                text += f"  [{format_time(duration)}]"
            entry = QListWidgetItem(text)
            entry.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(entry)
        if 0 <= current_index < self.list.count():
            self.list.setCurrentRow(current_index)

    def set_current(self, index: int) -> None:
        if 0 <= index < self.list.count():
            self.list.setCurrentRow(index)
