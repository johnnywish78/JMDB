import sqlite3

import pytest

from app.database import connection
from app.database.repositories.media import MediaRepository
from app.services.scanner import LibraryScanner, parse_media_filename


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    source_path = connection.DATABASE_PATH

    source = connection.sqlite3.connect(source_path)
    target = connection.sqlite3.connect(db_path)

    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    monkeypatch.setattr(connection, "DATABASE_PATH", db_path)

    return db_path


@pytest.fixture
def scanner(test_db):
    return LibraryScanner(MediaRepository())


def test_parse_movie_filename():
    parsed = parse_media_filename("Example.Movie.2024.mkv")
    assert parsed.title == "Example Movie"
    assert parsed.year == 2024
    assert parsed.media_type == "movie"
    assert parsed.season is None
    assert parsed.episode is None


def test_parse_series_episode_filename():
    parsed = parse_media_filename("Example.Show.S02E07.1080p.mkv")
    assert parsed.title == "Example Show"
    assert parsed.year is None
    assert parsed.media_type == "series"
    assert parsed.season == 2
    assert parsed.episode == 7


def test_parse_series_season_only_filename():
    parsed = parse_media_filename("Example.Show.S03.mkv")
    assert parsed.title == "Example Show"
    assert parsed.media_type == "series"
    assert parsed.season == 3
    assert parsed.episode is None


def test_scan_stores_parsed_year(scanner, tmp_path):
    root = tmp_path / "Movies"
    root.mkdir()

    movie = root / "Example.Movie.2024.mkv"
    movie.write_bytes(b"movie-data")

    result = scanner.scan_path(root)

    assert result.added == 1

    media = scanner.media_repository.list_media()

    assert len(media) == 1
    assert media[0]["title"] == "Example Movie"
    assert media[0]["year"] == 2024


def test_scan_path_adds_video_files(scanner, tmp_path):
    root = tmp_path / "Movies"
    root.mkdir()

    movie = root / "Example.Movie.2024.mkv"
    movie.write_bytes(b"movie-data")

    text_file = root / "ignore.txt"
    text_file.write_text("not media")

    nested = root / "nested"
    nested.mkdir()

    second_movie = nested / "Another.Movie.mp4"
    second_movie.write_bytes(b"second")

    result = scanner.scan_path(root)

    assert result.scanned == 2
    assert result.added == 2
    assert result.skipped == 0
    assert result.errors == 0

    repo = scanner.media_repository

    assert repo.count_media() == 2

    first_files = repo.get_media_files(1)
    second_files = repo.get_media_files(2)

    assert len(first_files) == 1
    assert len(second_files) == 1

    assert first_files[0]["file_size"] == len(b"movie-data")
    assert second_files[0]["file_size"] == len(b"second")


def test_scan_is_idempotent(scanner, tmp_path):
    root = tmp_path / "Movies"
    root.mkdir()

    movie = root / "Example.Movie.mkv"
    movie.write_bytes(b"movie")

    first = scanner.scan_path(root)

    assert first.scanned == 1
    assert first.added == 1
    assert first.skipped == 0

    second = scanner.scan_path(root)

    assert second.scanned == 1
    assert second.added == 0
    assert second.skipped == 1
    assert second.errors == 0

    assert scanner.media_repository.count_media() == 1


def test_scan_detects_series(scanner, tmp_path):
    root = tmp_path / "Series"
    root.mkdir()

    episode = root / "Example.Show.S01E03.mkv"
    episode.write_bytes(b"episode")

    result = scanner.scan_path(root)

    assert result.scanned == 1
    assert result.added == 1

    media = scanner.media_repository.list_media()

    assert len(media) == 1
    assert media[0]["media_type"] == "series"
    assert media[0]["title"] == "Example Show"


def test_scan_invalid_path(scanner, tmp_path):
    missing = tmp_path / "does-not-exist"

    result = scanner.scan_path(missing)

    assert result.scanned == 0
    assert result.added == 0
    assert result.skipped == 0
    assert result.errors == 1


def test_supported_video_extensions(scanner, tmp_path):
    root = tmp_path / "Videos"
    root.mkdir()

    extensions = [
        ".mkv",
        ".mp4",
        ".avi",
        ".mov",
        ".m4v",
        ".webm",
        ".wmv",
        ".mpeg",
        ".mpg",
        ".ts",
        ".m2ts",
        ".flv",
        ".divx",
    ]

    for index, extension in enumerate(extensions):
        (root / f"Video {index}{extension}").write_bytes(b"x")

    (root / "not-video.pdf").write_bytes(b"x")
    (root / "not-video.jpg").write_bytes(b"x")

    result = scanner.scan_path(root)

    assert result.scanned == len(extensions)
    assert result.added == len(extensions)
    assert result.skipped == 0
    assert result.errors == 0


def test_title_with_spaces_and_brackets():
    parsed = parse_media_filename(
        "Example_Title [2023] (1080p).mkv"
    )

    assert parsed.title == "Example Title"
    assert parsed.year == 2023


def test_parse_filename_without_metadata():
    parsed = parse_media_filename("Simple Video.mkv")

    assert parsed.title == "Simple Video"
    assert parsed.year is None
    assert parsed.media_type == "movie"
