"""Regression: Add library location (Settings → Library locations).

Proves the bug where "Add location" silently failed:
- the API used to answer HTTP 200 + {"ok": false} for invalid/duplicate
  folders, so the renderer showed a success toast and nothing was saved;
- now invalid → 400, duplicate → 409, valid → 201 with the real reason in
  ``detail``; a fresh process sees the same locations (persistence).
"""
from __future__ import annotations

import pytest

from app.bootstrap.dependencies import Dependencies
from tests.seedlib import seed_media_tree

from fastapi.testclient import TestClient


@pytest.fixture()
def client(jmdb_home):
    from app.api.auth import generate_token
    from app.api.context import APIContext
    from app.api.server import create_app

    token = generate_token()
    context = APIContext(Dependencies(), token)
    app = create_app(context=context, token=token, ui_dir=jmdb_home / "no-ui")
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        c.context = context
        yield c
    context.close()


def _add(c, path):
    return c.post("/api/library/locations", json={"path": str(path)})


def test_invalid_folder_rejected_with_400(client, tmp_path):
    response = _add(client, tmp_path / "does-not-exist")
    assert response.status_code == 400
    assert "readable directory" in response.json()["detail"]


def test_file_rejected_with_400(client, tmp_path):
    target = tmp_path / "afile.txt"
    target.write_text("not a directory")
    response = _add(client, target)
    assert response.status_code == 400


def test_valid_folder_added_with_201_and_listed(client, tmp_path):
    media = tmp_path / "media"
    seed_media_tree(media)
    response = _add(client, media / "Movies")
    assert response.status_code == 201
    body = response.json()
    assert body["ok"] is True
    assert body["added"]["path"].endswith("Movies")
    paths = [loc["path"] for loc in body["locations"]]
    assert any(p.endswith("Movies") for p in paths)


def test_duplicate_folder_rejected_with_409(client, tmp_path):
    media = tmp_path / "media"
    seed_media_tree(media)
    assert _add(client, media).status_code == 201
    second = _add(client, media)
    assert second.status_code == 409
    assert "already" in second.json()["detail"]


def test_same_folder_different_spelling_is_duplicate(client, tmp_path):
    """A trailing slash or ~ expansion must not create a shadow entry."""
    import os

    media = tmp_path / "media"
    seed_media_tree(media)
    assert _add(client, str(media)).status_code == 201
    assert _add(client, str(media) + "/").status_code in (201, 409)  # tolerated
    listed = client.get("/api/library").json()["locations"]
    assert len([l for l in listed if "media" in l["path"]]) == 1 or len(listed) == 2
    # the honest contract: never more than one entry for the same real folder
    canonical = {os.path.realpath(l["path"]) for l in listed}
    assert len(canonical) == len(listed)


def test_location_survives_restart(client, tmp_path, jmdb_home):
    media = tmp_path / "media"
    seed_media_tree(media)
    assert _add(client, media).status_code == 201

    # a brand-new dependency graph on the SAME home must see the location
    fresh = Dependencies()
    try:
        services = fresh.build()
        assert any(loc.path == str(media) for loc in services.library.locations())
    finally:
        fresh.close()


def test_scan_uses_saved_location_only(client, tmp_path):
    """POST /api/scan?location_id=N must scan ONLY that location."""
    from tests.seedlib import seed_media_tree

    one = tmp_path / "one"
    two = tmp_path / "two"
    seed_media_tree(one)
    seed_media_tree(two)
    assert _add(client, one).status_code == 201
    assert _add(client, two).status_code == 201
    locations = client.get("/api/library").json()["locations"]
    by_path = {loc["path"]: loc["id"] for loc in locations}
    one_id = by_path[str(one)]

    response = client.post(f"/api/scan?location_id={one_id}")
    assert response.status_code == 200
    assert response.json()["location_id"] == one_id

    import time

    deadline = time.time() + 15
    while time.time() < deadline:
        status = client.get("/api/scan/status").json()
        if not status["running"]:
            break
        time.sleep(0.1)
    assert status["running"] is False
    # only location `one` was scanned
    locs = {loc["id"]: loc for loc in client.get("/api/library").json()["locations"]}
    assert locs[one_id]["last_scan_status"] == "completed"
    other_id = by_path[str(two)]
    assert locs[other_id]["last_scan_status"] in ("", "never", None)


def test_scan_unknown_location_404(client):
    response = client.post("/api/scan?location_id=9999")
    assert response.status_code == 404
