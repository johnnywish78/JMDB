from pathlib import Path

import pytest

from app.database import connection
from app.database.repositories.media import MediaRepository


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    # Create a temporary database containing the current schema.
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
def repo(test_db):
    return MediaRepository()


def test_create_media_without_file(repo):
    media_id = repo.create_media(
        media_type="movie",
        title="The Matrix",
    )

    assert media_id > 0

    media = repo.get_media(media_id)

    assert media is not None
    assert media["id"] == media_id
    assert media["media_type"] == "movie"
    assert media["title"] == "The Matrix"
    assert media["sort_title"] == "the matrix"

    assert repo.get_media_files(media_id) == []


def test_create_media_with_year(repo):
    media_id = repo.create_media(
        media_type="movie",
        title="Example Movie",
        year=2024,
    )

    media = repo.get_media(media_id)

    assert media is not None
    assert media["year"] == 2024


def test_create_media_with_file(repo, tmp_path):
    movie_path = tmp_path / "The Matrix.mkv"
    movie_path.write_bytes(b"test-media")

    media_id = repo.create_media(
        media_type="movie",
        title="The Matrix",
        path=str(movie_path),
        file_size=movie_path.stat().st_size,
    )

    files = repo.get_media_files(media_id)

    assert len(files) == 1
    assert files[0]["media_id"] == media_id
    assert files[0]["path"] == str(movie_path)
    assert files[0]["file_size"] == 10


def test_list_media_sorted(repo):
    repo.create_media(media_type="movie", title="Zeta")
    repo.create_media(media_type="movie", title="Alpha")
    repo.create_media(media_type="series", title="Beta")

    movies = repo.list_media(media_type="movie")

    assert [item["title"] for item in movies] == ["Alpha", "Zeta"]


def test_list_media_pagination(repo):
    for title in ["Alpha", "Bravo", "Charlie"]:
        repo.create_media(
            media_type="movie",
            title=title,
        )

    first_page = repo.list_media(limit=2, offset=0)
    second_page = repo.list_media(limit=2, offset=2)

    assert [item["title"] for item in first_page] == [
        "Alpha",
        "Bravo",
    ]

    assert [item["title"] for item in second_page] == [
        "Charlie",
    ]


def test_count_media(repo):
    repo.create_media(media_type="movie", title="Movie One")
    repo.create_media(media_type="movie", title="Movie Two")
    repo.create_media(media_type="series", title="Series One")

    assert repo.count_media() == 3
    assert repo.count_media("movie") == 2
    assert repo.count_media("series") == 1


def test_delete_media_cascades_files(repo, tmp_path):
    media_path = tmp_path / "movie.mkv"
    media_path.write_bytes(b"test")

    media_id = repo.create_media(
        media_type="movie",
        title="Delete Me",
        path=str(media_path),
        file_size=4,
    )

    assert repo.get_media(media_id) is not None
    assert len(repo.get_media_files(media_id)) == 1

    assert repo.delete_media(media_id) is True

    assert repo.get_media(media_id) is None
    assert repo.get_media_files(media_id) == []

    assert repo.delete_media(media_id) is False
