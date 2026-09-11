import sqlite3

import pytest

from app.database import connection
from app.database.repositories.library import LibraryRepository


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
def repo(test_db):
    return LibraryRepository()


def test_create_and_get_library(repo):
    library_id = repo.create_library("Movies")

    assert library_id > 0

    library = repo.get_library(library_id)

    assert library is not None
    assert library["id"] == library_id
    assert library["name"] == "Movies"
    assert library["created_at"]


def test_empty_library_name_rejected(repo):
    with pytest.raises(ValueError, match="Library name cannot be empty"):
        repo.create_library("   ")


def test_list_libraries_sorted(repo):
    repo.create_library("Zeta")
    repo.create_library("alpha")
    repo.create_library("Beta")

    libraries = repo.list_libraries()

    assert [item["name"] for item in libraries] == [
        "alpha",
        "Beta",
        "Zeta",
    ]


def test_add_and_get_paths(repo, tmp_path):
    library_id = repo.create_library("Movies")

    path_one = tmp_path / "Movies"
    path_two = tmp_path / "More Movies"

    path_one.mkdir()
    path_two.mkdir()

    path_id_one = repo.add_path(library_id, str(path_one))
    path_id_two = repo.add_path(library_id, str(path_two))

    assert path_id_one > 0
    assert path_id_two > 0

    paths = repo.get_paths(library_id)

    assert len(paths) == 2
    assert {item["path"] for item in paths} == {
        str(path_one.resolve()),
        str(path_two.resolve()),
    }


def test_add_path_requires_existing_library(repo, tmp_path):
    path = tmp_path / "Movies"
    path.mkdir()

    with pytest.raises(ValueError, match="Library not found"):
        repo.add_path(999999, str(path))


def test_duplicate_library_name_rejected(repo):
    repo.create_library("Movies")

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_library("Movies")


def test_duplicate_path_rejected(repo, tmp_path):
    library_id = repo.create_library("Movies")

    path = tmp_path / "Movies"
    path.mkdir()

    repo.add_path(library_id, str(path))

    with pytest.raises(sqlite3.IntegrityError):
        repo.add_path(library_id, str(path))


def test_get_library_for_path(repo, tmp_path):
    library_id = repo.create_library("Movies")

    path = tmp_path / "Movies"
    path.mkdir()

    repo.add_path(library_id, str(path))

    result = repo.get_library_for_path(str(path))

    assert result is not None
    assert result["library_id"] == library_id
    assert result["library_name"] == "Movies"
    assert result["path"] == str(path.resolve())


def test_remove_path(repo, tmp_path):
    library_id = repo.create_library("Movies")

    path = tmp_path / "Movies"
    path.mkdir()

    path_id = repo.add_path(library_id, str(path))

    assert repo.remove_path(path_id) is True
    assert repo.remove_path(path_id) is False
    assert repo.get_paths(library_id) == []


def test_delete_library_cascades_paths(repo, tmp_path):
    library_id = repo.create_library("Movies")

    path = tmp_path / "Movies"
    path.mkdir()

    repo.add_path(library_id, str(path))

    assert len(repo.get_paths(library_id)) == 1

    assert repo.delete_library(library_id) is True

    assert repo.get_library(library_id) is None
    assert repo.get_paths(library_id) == []
    assert repo.delete_library(library_id) is False


def test_missing_library_returns_none(repo):
    assert repo.get_library(999999) is None
