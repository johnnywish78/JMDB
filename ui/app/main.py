"""UI entry helpers."""
from __future__ import annotations

from ui.app.main_window import MainWindow


def create_main_window(container) -> MainWindow:
    """MainWindow is constructed lazily so a fresh QApplication already exists."""
    return MainWindow(container)
