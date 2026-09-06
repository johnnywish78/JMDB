"""Subtitle selection dialog: embedded tracks + external files."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class SubtitleDialog(QDialog):
    """Returns a SubtitleOption or None (None = disable subtitles)."""

    def __init__(self, options: list, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select subtitles")
        self.setMinimumSize(420, 320)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list)

        off = QListWidgetItem("Off (disable subtitles)")
        off.setData(0x0100, None)  # Qt.UserRole
        self.list.addItem(off)
        for option in options:
            item = QListWidgetItem(option.label)
            item.setData(0x0100, option)
            self.list.addItem(item)
        self.list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self):
        item = self.list.currentItem()
        return item.data(0x0100) if item else None
