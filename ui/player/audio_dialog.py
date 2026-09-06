"""Audio track selection dialog."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class AudioDialog(QDialog):
    def __init__(self, tracks: list, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select audio track")
        self.setMinimumSize(420, 300)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list)
        if not tracks:
            self.list.addItem("No audio tracks reported by this backend")
            self.list.setEnabled(False)
        for index, track in enumerate(tracks):
            item = QListWidgetItem(track.label())
            item.setData(0x0100, track)
            self.list.addItem(item)
        if tracks:
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
