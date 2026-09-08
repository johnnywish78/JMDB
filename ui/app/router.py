"""Router: named screens in a QStackedWidget, factories get (container, **params)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QStackedWidget, QWidget


@dataclass
class UIState:
    current: str = "home"
    params: dict[str, Any] = field(default_factory=dict)


class Router(QObject):
    navigated = pyqtSignal(str)

    def __init__(self, stack: QStackedWidget, container, parent=None):
        super().__init__(parent)
        self.stack = stack
        self.container = container
        self.state = UIState()
        self._factories: dict[str, Callable[..., QWidget]] = {}
        self._pages: dict[str, QWidget] = {}

    def register(self, name: str, factory: Callable[..., QWidget]) -> None:
        self._factories[name] = factory

    def names(self) -> list[str]:
        return list(self._factories.keys())

    def navigate(self, name: str, **params) -> None:
        if name not in self._factories:
            name = "home"
        key = f"{name}|{sorted(params.items())}"
        if key not in self._pages:
            page = self._factories[name](self.container, **params)
            self._pages[key] = page
            self.stack.addWidget(page)
        page = self._pages[key]
        self.state.current = name
        self.state.params = params
        self.stack.setCurrentWidget(page)
        self.navigated.emit(name)
        if hasattr(page, "on_show"):
            page.on_show()

    def invalidate(self, prefix: str = "") -> None:
        """Drop cached pages (e.g. after library changes) so they rebuild."""
        for key in list(self._pages.keys()):
            if key.startswith(prefix):
                page = self._pages.pop(key)
                self.stack.removeWidget(page)
                page.deleteLater()
