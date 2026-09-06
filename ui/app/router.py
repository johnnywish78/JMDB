"""Router: named routes → screen factories. No dead navigation allowed."""
from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtWidgets import QStackedWidget

logger = logging.getLogger(__name__)


class RouteError(KeyError):
    pass


class Router(QStackedWidget):
    """Central navigation stack. Every route must have a registered screen."""

    def __init__(self, context_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._factories: dict[str, Callable] = {}
        self._screens: dict[str, object] = {}
        self._context_factory = context_factory
        self._history: list[str] = []

    def register(self, route: str, factory: Callable) -> None:
        if route in self._factories:
            raise RouteError(f"route registered twice: {route}")
        self._factories[route] = factory
        logger.debug("route registered: %s", route)

    def routes(self) -> list[str]:
        return sorted(self._factories)

    def routes_with_titles(self) -> list[tuple[str, str]]:
        """Registered (route, title) pairs, using each screen's title attr."""
        pairs = []
        for route, factory in self._factories.items():
            title = getattr(factory, "title", None) or route.replace("_", " ").title()
            pairs.append((route, title))
        return pairs

    def has_route(self, route: str) -> bool:
        return route in self._factories

    def _ensure(self, route: str):
        if route not in self._screens:
            if route not in self._factories:
                raise RouteError(
                    f"No screen registered for route '{route}'. Registered: {self.routes()}"
                )
            screen = self._factories[route](self._context_factory())
            self.addWidget(screen)
            self._screens[route] = screen
        return self._screens[route]

    def navigate(self, route: str, **params) -> None:
        screen = self._ensure(route)
        current = self._history[-1] if self._history else ""
        if current != route:
            self._history.append(route)
            self._history = self._history[-32:]
        handler = getattr(screen, "enter", None)
        if handler is not None:
            handler(**params)
        refresh = getattr(screen, "refresh", None)
        if refresh is not None:
            refresh()
        self.setCurrentWidget(screen)

    def back(self) -> None:
        if len(self._history) >= 2:
            self._history.pop()
            route = self._history[-1]
            self._history.pop()  # navigate re-appends
            self.navigate(route)

    def current_route(self) -> str:
        return self._history[-1] if self._history else ""
