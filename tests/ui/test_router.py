"""Router unit tests (offscreen)."""
from __future__ import annotations

import pytest

from PyQt6.QtWidgets import QLabel, QWidget

from ui.app.router import RouteError, Router


class StubScreen(QWidget):
    title = "Stub"

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.entered = []
        self.refreshed = 0

    def enter(self, **params):
        self.entered.append(params)

    def refresh(self):
        self.refreshed += 1


@pytest.fixture()
def router():
    r = Router(lambda: {"fake": "context"})
    r.register("a", StubScreen)
    r.register("b", StubScreen)
    return r


def _pump(app, times=5):
    for _ in range(times):
        app.processEvents()


def test_register_and_routes(router):
    assert router.routes() == ["a", "b"]
    assert router.has_route("a")
    assert not router.has_route("nope")


def test_routes_with_titles_uses_screen_title(router):
    pairs = dict(router.routes_with_titles())
    assert pairs["a"] == "Stub"


def test_navigate_creates_screen_once_and_enters(qtbot, router):
    router.navigate("a", movie_id=7)
    screen = router.widget(0)
    assert isinstance(screen, StubScreen)
    assert screen.context == {"fake": "context"}
    assert screen.entered == [{"movie_id": 7}]
    assert screen.refreshed == 1

    # second navigate: same instance, re-entered + refreshed
    router.navigate("a")
    assert router.widget(0) is screen
    assert screen.entered == [{"movie_id": 7}, {}]
    assert screen.refreshed == 2


def test_back_returns_to_previous(qtbot, router):
    router.navigate("a")
    router.navigate("b")
    assert router.current_route() == "b"
    router.back()
    assert router.current_route() == "a"


def test_unknown_route_raises(router):
    with pytest.raises(RouteError):
        router.navigate("missing")


def test_duplicate_registration_raises(router):
    with pytest.raises(RouteError):
        router.register("a", StubScreen)
