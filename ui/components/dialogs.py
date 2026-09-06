"""Common dialogs: input, confirm, scan progress, about."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ui.app.context import icon


def confirm(parent, title: str, message: str) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Icon.Question)
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


def info(parent, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def error(parent, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def text_input(parent, title: str, label: str, default: str = "") -> tuple[str, bool]:
    return QInputDialog.getText(parent, title, label, text=default)


class ScanProgressDialog(QDialog):
    """Non-blocking scan progress with pause/resume/cancel."""

    def __init__(self, parent, location_label: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scanning library")
        self.setMinimumWidth(460)
        self.setModal(False)
        layout = QVBoxLayout(self)
        self.status = QLabel(f"Scanning {location_label}…")
        layout.addWidget(self.status)
        self.detail = QLabel("")
        self.detail.setObjectName("MutedLabel")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)  # indeterminate until totals known
        layout.addWidget(self.bar)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._toggle_pause)
        layout.addWidget(self.pause_button)
        self.cancel_button = QPushButton("Cancel scan")
        self.cancel_button.setObjectName("DangerButton")
        layout.addWidget(self.cancel_button)
        self._paused = False

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.pause_button.setText("Resume" if self._paused else "Pause")

    def update_progress(self, files_seen: int, current_path: str = "") -> None:
        self.status.setText(f"Scanning… {files_seen} files seen")
        self.detail.setText(current_path)

    def is_paused(self) -> bool:
        return self._paused


class AboutDialog(QDialog):
    def __init__(self, parent, version: str, diagnostics_text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("About JMDB")
        self.setMinimumSize(520, 420)
        layout = QVBoxLayout(self)
        title = QLabel("JMDB — Johnny Media Database")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)
        version_label = QLabel(f"Version {version}")
        version_label.setObjectName("MutedLabel")
        layout.addWidget(version_label)
        from PyQt6.QtWidgets import QTextEdit

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlainText(diagnostics_text)
        layout.addWidget(self.details)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
