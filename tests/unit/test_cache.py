"""Tests for metadata cache — TTL, invalidation, corruption, provider tracking."""
from __future__ import annotations

import time

import pytest

from app.database.connection import Database
from app.database.migrations import migrate
from app.metadata.cache import MetadataCache


@pytest.fixture()
def cache(tmp_path):
    db = Database(tmp_path / "test.db")
    db.connect()
    migrate(db)
    yield MetadataCache(db)
    db.close()


def test_positive_cache_hit(cache):
    cache.set("movie", "moonraker|1979", {"title": "Moonraker", "year": 1979}, provider="TMDBProvider")
    result = cache.get("movie", "moonraker|1979", ttl_s=60 * 60 * 24 * 30, provider="TMDBProvider")
    assert result is not None
    assert result["title"] == "Moonraker"


def test_cache_miss(cache):
    result = cache.get("movie", "nonexistent|0", ttl_s=99999, provider="TMDBProvider")
    assert result is None


def test_ttl_expiry(cache):
    cache.set("movie", "old|0", {"title": "Old"}, provider="TMDBProvider")
    # Manually backdate the entry
    cache.db.execute(
        "UPDATE metadata_cache SET created_at=? WHERE bucket='movie' AND key='old|0'",
        (int(time.time()) - 99999,))
    result = cache.get("movie", "old|0", ttl_s=3600, provider="TMDBProvider")
    assert result is None


def test_corrupted_payload_returns_none(cache):
    cache.db.execute(
        "INSERT INTO metadata_cache (bucket, key, provider, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("movie", "corrupt|0", "", "NOT VALID JSON", int(time.time())))
    result = cache.get("movie", "corrupt|0", ttl_s=99999, provider="")
    assert result is None


def test_get_any_provider_finds_entry(cache):
    cache.set("movie", "key|0", {"title": "A"}, provider="TMDBProvider")
    result = cache.get_any_provider("movie", "key|0", ttl_s=99999)
    assert result is not None
    assert result["title"] == "A"


def test_clear_by_bucket(cache):
    cache.set("movie", "k1|0", {"t": 1}, provider="p1")
    cache.set("movie", "k2|0", {"t": 2}, provider="p2")
    cache.set("series", "k3|0", {"t": 3}, provider="p1")
    n = cache.clear(bucket="movie")
    assert n == 2
    assert cache.get("movie", "k1|0", 99999) is None
    assert cache.get("series", "k3|0", 99999) is not None


def test_clear_by_key_prefix(cache):
    cache.set("movie", "bond007|0", {"t": 1}, provider="p1")
    cache.set("movie", "bond008|0", {"t": 2}, provider="p2")
    cache.set("movie", "matrix|0", {"t": 3}, provider="p1")
    n = cache.clear(key_prefix="bond")
    assert n == 2
    assert cache.get("movie", "matrix|0", 99999) is not None


def test_clear_all(cache):
    cache.set("movie", "k1|0", {"t": 1})
    cache.set("series", "k2|0", {"t": 2})
    n = cache.clear()
    assert n == 2
    assert cache.stats()["total"] == 0


def test_stats(cache):
    cache.set("movie", "m1|0", {"t": 1})
    cache.set("movie", "m2|0", {"t": 2})
    cache.set("series", "s1|0", {"t": 3})
    stats = cache.stats()
    assert stats["movies"] == 2
    assert stats["series"] == 1
    assert stats["total"] == 3


def test_provider_specific_get(cache):
    cache.set("movie", "k|0", {"provider": "TMDB"}, provider="TMDBProvider")
    cache.set("movie", "k|0", {"provider": "OMDb"}, provider="OMDbProvider")
    tmdb = cache.get("movie", "k|0", 99999, provider="TMDBProvider")
    omdb = cache.get("movie", "k|0", 99999, provider="OMDbProvider")
    assert tmdb["provider"] == "TMDB"
    assert omdb["provider"] == "OMDb"
