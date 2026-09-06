"""Shared UI component unit tests (offscreen)."""
from __future__ import annotations

import pytest

from PyQt6.QtWidgets import QApplication, QWidget

from ui.components.poster_card import PosterCard
from ui.components.season_card import SeasonCard
from ui.components.states import EmptyState
from ui.player.controls import format_time


SEASON = {
    "id": 3,
    "season_number": 2,
    "title": "Season 2",
    "episode_count": 10,
    "watched_count": 4,
    "overview": "Things get complicated.",
    "poster_path": "",
}


def test_format_time():
    assert format_time(0) == "0:00"
    assert format_time(59.4) == "0:59"
    assert format_time(61) == "1:01"
    assert format_time(3600 + 59) == "1:00:59"
    assert format_time(2 * 3600 + 5 * 60 + 9) == "2:05:09"


def test_poster_card_shows_title_year_and_emits(qtbot):
    card = PosterCard({"title": "Night Runner", "year": 2024}, width=120)
    qtbot.addWidget(card)
    assert card.title.text() == "Night Runner"
    assert card.subtitle.text() == "2024"

    with qtbot.waitSignal(card.clicked):
        card.clicked.emit({"title": "Night Runner"})


def test_poster_card_progress_visible_when_position(qtbot):
    card = PosterCard(
        {"title": "Ep", "position_seconds": 500, "duration_seconds": 1000},
        show_progress=True,
    )
    qtbot.addWidget(card)
    assert not card.progress.isHidden()

    bare = PosterCard({"title": "Ep"}, show_progress=True)
    qtbot.addWidget(bare)
    assert bare.progress.isHidden()


def test_season_card_metadata_and_signals(qtbot):
    card = SeasonCard(SEASON)
    qtbot.addWidget(card)
    assert card.season_id == 3
    assert card.mark_watched_button.isEnabled()

    with qtbot.waitSignal(card.open_requested):
        card.open_requested.emit(3)
    with qtbot.waitSignal(card.mark_watched):
        card.mark_watched.emit(3)


def test_season_card_complete_season_disables_mark_watched(qtbot):
    card = SeasonCard(dict(SEASON, watched_count=10))
    qtbot.addWidget(card)
    assert not card.mark_watched_button.isEnabled()
    assert "✓" in card.mark_watched_button.text()


def test_empty_state_optional_action(qtbot):
    plain = EmptyState("Nothing here", "Explanation text")
    qtbot.addWidget(plain)
    assert plain.action_button is None

    actionable = EmptyState("Nothing here", "Explanation", "Do the thing")
    qtbot.addWidget(actionable)
    assert actionable.action_button is not None

    with qtbot.waitSignal(actionable.action):
        actionable.action_button.click()


def test_statistics_widgets(qtbot):
    from ui.screens.statistics import BarList, StatCard

    stat = StatCard("12 h", "Watch time")
    qtbot.addWidget(stat)

    bars = BarList([("Drama", 10), ("Sci-Fi", 5), ("Comedy", 0)])
    qtbot.addWidget(bars)
    labels = bars.findChildren(QWidget)
    assert any("Drama" in w.text() for w in labels if hasattr(w, "text"))
    assert any("Sci-Fi" in w.text() for w in labels if hasattr(w, "text"))
