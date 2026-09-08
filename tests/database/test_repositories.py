"""Tests for database repositories — upsert idempotency, foreign keys, migrations."""
from __future__ import annotations

import pytest

from app.database.connection import Database
from app.database.migrations import migrate
from app.database.repositories import (
    EpisodeRepository,
    LibraryStateRepository,
    MediaRepository,
    ProgressRepository,
)


@pytest.fixture()
def repos(tmp_path):
    db = Database(tmp_path / "test.db")
    db.connect()
    migrate(db)
    return type("Repos", (), {
        "media": MediaRepository(db),
        "episodes": EpisodeRepository(db),
        "state": LibraryStateRepository(db),
        "progress": ProgressRepository(db),
        "db": db,
    })()


def test_upsert_is_idempotent(repos):
    id1 = repos.media.upsert("movie", "The Matrix", 1999)
    id2 = repos.media.upsert("movie", "The Matrix", 1999)
    assert id1 == id2


def test_upsert_different_year_is_different_record(repos):
    id1 = repos.media.upsert("movie", "Casino Royale", 2006)
    id2 = repos.media.upsert("movie", "Casino Royale", 2003)
    assert id1 != id2


def test_upsert_updates_only_passed_fields(repos):
    mid = repos.media.upsert("movie", "Goldfinger", 1964, rating=8.0, overview="spy")
    # Update only runtime_min
    repos.media.upsert("movie", "Goldfinger", 1964, runtime_min=100)
    row = repos.media.get(mid)
    assert row["rating"] == 8.0
    assert row["overview"] == "spy"
    assert row["runtime_min"] == 100


def test_list_kind_filter(repos):
    repos.media.upsert("movie", "Movie A", 2000)
    repos.media.upsert("show", "Show A", 2020)
    movies = repos.media.list("movie")
    shows = repos.media.list("show")
    assert len(movies) == 1
    assert len(shows) == 1
    assert movies[0]["kind"] == "movie"
    assert shows[0]["kind"] == "show"


def test_favorites_and_watchlist_toggle(repos):
    mid = repos.media.upsert("movie", "Test", 2000)
    assert repos.state.toggle_favorite(mid) is True
    assert repos.state.toggle_favorite(mid) is False
    assert mid not in repos.state.favorites()
    assert repos.state.toggle_watchlist(mid) is True
    assert mid in repos.state.watchlist()


def test_progress_save_and_resume(repos):
    key = "m:1"
    repos.progress.set_position(key, 120, 7200)
    saved = repos.progress.get(key)
    assert saved is not None
    assert saved["position_s"] == 120
    assert saved["duration_s"] == 7200
    repos.progress.clear(key)
    assert repos.progress.get(key) is None


def test_episode_upsert_idempotent(repos):
    show_id = repos.media.upsert("show", "Arcane", 2021)
    ep1 = repos.episodes.upsert(show_id, 1, 1, file_path="/a/s01e01.mkv")
    ep2 = repos.episodes.upsert(show_id, 1, 1, file_path="/a/s01e01_v2.mkv")
    assert ep1 == ep2
    eps = repos.episodes.for_show(show_id)
    assert len(eps) == 1
    assert eps[0]["file_path"] == "/a/s01e01_v2.mkv"


def test_delete_file_missing_removes_gone_files(repos):
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as f:
        fp = f.name
    mid = repos.media.upsert("movie", "Temp Movie", 2020, file_path=fp)
    os.unlink(fp)
    n = repos.media.delete_file_missing()
    assert n == 1
    assert repos.media.get(mid) is None


def test_distinct_genres(repos):
    repos.media.upsert("movie", "Action Movie", 2020, genres=["Action", "Sci-Fi"])
    repos.media.upsert("movie", "Romance Movie", 2021, genres=["Romance"])
    genres = repos.media.distinct_genres("movie")
    assert set(genres) == {"Action", "Sci-Fi", "Romance"}


def test_schema_version_increments(tmp_path):
    db = Database(tmp_path / "v.db")
    db.connect()
    v = migrate(db)
    assert v >= 3  # at least migration 3 (provider column)
