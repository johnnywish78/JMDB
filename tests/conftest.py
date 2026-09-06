"""Shared test fixtures.

Everything is hermetic: JMDB_HOME points at a temp directory, Qt runs
offscreen, and no network is touched.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure offscreen Qt before any PyQt6 import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-dev-shm-usage"
)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def jmdb_home(tmp_path, monkeypatch):
    home = tmp_path / "jmdb-home"
    home.mkdir()
    monkeypatch.setenv("JMDB_HOME", str(home))
    return home


@pytest.fixture()
def database(jmdb_home):
    from app.database.connection import Database
    from app.database.migrations import apply_migrations

    db = Database(jmdb_home / "database" / "jmdb.db")
    apply_migrations(db)
    yield db
    db.close()


@pytest.fixture()
def repos(database):
    from app.database.repositories import Repositories

    return Repositories(database)


@pytest.fixture()
def profile(repos):
    return repos.profiles.ensure_default()


@pytest.fixture()
def events():
    from app.domain.events import EventBus

    return EventBus()


@pytest.fixture()
def scanner(database, repos, events):
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner, ScanOptions

    return LibraryScanner(
        database, repos, events, ProbeTools(),
        ScanOptions(probe_files=False, checksum_min_mb=0),
    )


@pytest.fixture()
def media_tree(tmp_path):
    """A realistic media directory tree (empty files, real names)."""
    root = tmp_path / "media"
    (root / "Movies" / "Night Runner (2024)").mkdir(parents=True)
    (root / "Movies" / "Night Runner (2024)" / "Night.Runner.2024.1080p.BluRay.x264.mkv").write_bytes(b"x" * 10)
    (root / "Movies" / "Night Runner (2024)" / "poster.jpg").write_bytes(b"x" * 10)
    (root / "Movies" / "Cosmic Drift").mkdir(parents=True)
    (root / "Movies" / "Cosmic Drift" / "Cosmic.Drift.2019.720p.WEBRip.mp4").write_bytes(b"x" * 10)
    (root / "TV" / "Solar Winds" / "Season 01").mkdir(parents=True)
    (root / "TV" / "Solar Winds" / "Season 01" / "Solar.Winds.S01E01.720p.mkv").write_bytes(b"x" * 10)
    (root / "TV" / "Solar Winds" / "Season 01" / "Solar.Winds.S01E02-E03.720p.mkv").write_bytes(b"x" * 10)
    (root / "TV" / "Desert Show" / "Season 2").mkdir(parents=True)
    (root / "TV" / "Desert Show" / "Season 2" / "Desert Show - 2x05.mkv").write_bytes(b"x" * 10)
    (root / "Music" / "Aurora B" / "Midnight Sessions").mkdir(parents=True)
    (root / "Music" / "Aurora B" / "Midnight Sessions" / "01 - First Light.mp3").write_bytes(b"x" * 10)
    (root / "Music" / "Aurora B" / "Midnight Sessions" / "02 - Dust and Echoes.mp3").write_bytes(b"x" * 10)
    return root
