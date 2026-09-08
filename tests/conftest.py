"""Shared fixtures — pure-python only, no Qt imports: `pytest` runs headless."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Database
from app.database.migrations import migrate
from app.database.repositories import (
    BookmarkRepository,
    EpisodeRepository,
    HistoryRepository,
    LibraryStateRepository,
    MediaRepository,
    PeopleRepository,
    ProgressRepository,
)


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.connect()
    migrate(database)
    yield database
    database.close()


@pytest.fixture()
def repos(db):
    return type(
        "Repos", (), {
            "media": MediaRepository(db),
            "episodes": EpisodeRepository(db),
            "people": PeopleRepository(db),
            "state": LibraryStateRepository(db),
            "progress": ProgressRepository(db),
            "history": HistoryRepository(db),
            "bookmarks": BookmarkRepository(db),
            "db": db,
        })()


@pytest.fixture()
def seeded_movie(repos):
    mid = repos.media.upsert("movie", "The Matrix", 1999, genres=["Sci-Fi", "Action"],
                             rating=8.7, runtime_min=136, overview="A hacker wakes up.")
    return mid
