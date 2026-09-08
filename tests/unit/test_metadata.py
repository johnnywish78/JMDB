"""Tests for metadata manager — enrichment, re-enrichment, OMDb fallback."""
from __future__ import annotations

import pytest

from app.database.connection import Database
from app.database.migrations import migrate
from app.database.repositories import MediaRepository
from app.domain.enums import MediaKind
from app.domain.models import DetectedMedia
from app.metadata.cache import MetadataCache
from app.metadata.manager import MetadataManager


@pytest.fixture()
def mgr(tmp_path):
    db = Database(tmp_path / "test.db")
    db.connect()
    migrate(db)
    cache = MetadataCache(db)
    # Pass empty keys so no providers are configured (tests that degrade gracefully)
    mgr = MetadataManager(cache, tmdb_key="", omdb_key="")
    return mgr, db


@pytest.fixture()
def repos(tmp_path):
    db = Database(tmp_path / "test2.db")
    db.connect()
    migrate(db)
    return MediaRepository(db), db


def test_no_providers_returns_none(mgr):
    media_id, _db = mgr
    result = media_id.enrich(1, DetectedMedia(path="/tmp/x.mkv", kind=MediaKind.MOVIE, title="Test"))
    assert result is None


def test_music_not_enriched_as_movie(repos):
    media_repo, db = repos
    mid = media_repo.upsert("movie", "Test Song", None, file_path="/tmp/song.mp3")
    # Manager with no providers — should just return None for music too
    mgr = MetadataManager(MetadataCache(db), tmdb_key="", omdb_key="")
    result = mgr.enrich(mid, DetectedMedia(path="/tmp/song.mp3", kind=MediaKind.MUSIC, title="Song"))
    assert result is None


def test_re_enrich_preserves_existing_when_no_match(repos):
    media_repo, db = repos
    mid = media_repo.upsert("movie", "Moonraker", 1979,
                            rating=7.5, tmdb_id=698, poster_path="http://example.com/p.jpg")
    mgr = MetadataManager(MetadataCache(db), tmdb_key="", omdb_key="")
    detected = DetectedMedia(path="/tmp/moonraker.mkv", kind=MediaKind.MOVIE, title="Moonraker", year=1979)
    result = mgr.re_enrich(mid, detected, media_repo=media_repo, clear_cache=True)
    assert result is None
    # Existing data preserved
    row = media_repo.get(mid)
    assert row["rating"] == 7.5
    assert row["tmdb_id"] == 698
    assert row["poster_path"] == "http://example.com/p.jpg"


def test_apply_metadata_does_not_zero_good_fields(repos):
    """Apply metadata must not overwrite existing good values with empty ones."""
    media_repo, _db = repos
    mid = media_repo.upsert("movie", "Moonraker", 1979, rating=7.5, tmdb_id=698)
    # Simulate a partial metadata payload (e.g. OMDb has no backdrop)
    meta = {"original_title": "", "rating": 0.0, "overview": "", "runtime_min": 0,
            "genres": [], "year": 1979, "imdb_id": "", "tmdb_id": None,
            "poster_url": None, "backdrop_url": None}
    media_repo.apply_metadata(mid, meta)
    row = media_repo.get(mid)
    # Rating and tmdb_id should be preserved (new values are empty/None)
    assert row["rating"] == 7.5
    assert row["tmdb_id"] == 698


def test_merge_metadata_prefers_primary(repos):
    db = Database(":memory:")
    db.connect()
    migrate(db)
    mgr = MetadataManager(MetadataCache(db), tmdb_key="", omdb_key="")
    primary = {"title": "A", "rating": 8.0, "poster_url": "http://p1", "imdb_id": ""}
    secondary = {"title": "B", "rating": 0.0, "poster_url": None, "imdb_id": "tt123"}
    merged = mgr.merge_metadata(primary, secondary)
    assert merged["rating"] == 8.0
    assert merged["poster_url"] == "http://p1"
    assert merged["imdb_id"] == "tt123"  # secondary fills missing field
