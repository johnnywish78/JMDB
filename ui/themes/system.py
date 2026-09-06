"""Theme management: dark / light / system, applied instantly."""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from app.domain.events import EventBus, ThemeChanged

logger = logging.getLogger(__name__)

THEMES_DIR = Path(__file__).resolve().parent


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)

    def __init__(self, app: QApplication, settings, events: EventBus) -> None:
        super().__init__()
        self.app = app
        self.settings = settings
        self.events = events
        self._current = ""

    # -- system palette detection ------------------------------------------------
    def _system_theme(self) -> str:
        try:
            scheme = self.app.styleHints().colorScheme()
            if scheme is not None:
                return "dark" if scheme == scheme.Dark else "light"
        except Exception:
            pass
        palette = self.app.palette()
        try:
            lightness = palette.color(QPalette.ColorRole.Window).lightness()
            return "light" if lightness > 128 else "dark"
        except Exception:
            return "dark"

    def effective_theme(self) -> str:
        setting = str(self.settings.get("theme"))
        if setting == "system":
            return self._system_theme()
        return setting

    # -- apply ------------------------------------------------------------------
    def apply(self) -> str:
        theme = self.effective_theme()
        if theme == self._current:
            return theme
        qss_file = THEMES_DIR / f"{theme}.qss"
        try:
            qss = qss_file.read_text("utf-8")
        except OSError:
            logger.error("theme file missing: %s", qss_file)
            qss = ""
        self.app.setStyleSheet(qss)
        self._current = theme
        self.theme_changed.emit(theme)
        self.events.publish(ThemeChanged(theme=theme))
        logger.info("theme applied: %s", theme)
        return theme

    def set_theme(self, theme: str, persist: bool = True) -> None:
        if theme not in ("dark", "light", "system"):
            raise ValueError(f"unknown theme: {theme}")
        if persist:
            self.settings.set("theme", theme)
        self.apply()

    @property
    def current(self) -> str:
        return self._current
