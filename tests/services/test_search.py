"""Tests for search engine — FTS5 and LIKE fallback."""
from __future__ import annotations

import pytest

from app.search.engine import SearchEngine, SearchFilters


@pytest.fixture()
def engine(tmp_path):
    from app.database.connection import Database
    from app.database.migrations import migrate
    db = Database(tmp_path / "test.db")
    db.connect()
    migrate(db)
    yield SearchEngine(db), db
    db.close()


def test_search_finds_and_filters(engine):
    se, db = engine
    from app.database.repositories import MediaRepository
    mr = MediaRepository(db)
    a = mr.upsert("movie", "Mad Max: Fury Road", 2015, genres=["Action"], rating=8.1, runtime_min=120)
    b = mr.upsert("movie", "Pride & Prejudice", 2005, genres=["Romance"], rating=7.8, runtime_min=127)
    hits = se.search("mad")
    assert hits and hits[0]["id"] == a
    hits = se.search("prejudice", SearchFilters(genre="Romance"))
    assert hits and hits[0]["id"] == b
    assert se.search("mad", SearchFilters(genre="Romance")) == []


def test_search_empty_query_returns_all(engine):
    se, db = engine
    from app.database.repositories import MediaRepository
    mr = MediaRepository(db)
    mr.upsert("movie", "Test Film", 2020)
    hits = se.search("")
    assert len(hits) >= 1


def test_search_no_results(engine):
    se, _ = engine
    hits = se.search("zzzzz_nonexistent")
    assert hits == []
