"""End-to-end tests for the FastAPI backend against a real, isolated SQLite DB.

These boot the *actual* FastAPI app (same object Electron talks to) with the
data directory redirected to a temp path, then exercise the real endpoints the
renderer uses: settings, favorites, watchlist, history, progress/resume,
scanner, detail/episodes, search, stats, recommendations, services, bookmarks.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.paths import AppPaths


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.api.server as server
    import app.bootstrap.dependencies as deps

    monkeypatch.setattr(deps, "AppPaths", lambda: AppPaths(root=tmp_path))
    server._container = None  # force fresh container bound to tmp data dir
    with TestClient(server.app) as c:
        yield c
    server._container = None


def _scan(client, folder: str):
    r = client.post("/api/scan", json={"folders": [folder], "enrich": False})
    assert r.status_code == 200 and r.json()["ok"] is True
    # poll until finished
    for _ in range(100):
        st = client.get("/api/scan/status").json()
        if not st["running"]:
            return st
        time.sleep(0.05)
    raise AssertionError("scan did not finish")


def _seed_media(tmp_path):
    lib = tmp_path / "media"
    (lib / "movies").mkdir(parents=True)
    (lib / "tv" / "My Show" / "Season 1").mkdir(parents=True)
    (lib / "movies" / "The Matrix (1999).mp4").write_bytes(b"x")
    (lib / "movies" / "Inception 2010.mkv").write_bytes(b"x")
    (lib / "tv" / "My Show" / "Season 1" / "My Show S01E01.mkv").write_bytes(b"x")
    (lib / "tv" / "My Show" / "Season 1" / "My Show S01E02.mkv").write_bytes(b"x")
    return str(lib)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_settings_persist(client, tmp_path):
    r = client.patch("/api/settings", json={"theme": "light", "autoplay_next": False})
    assert r.status_code == 200
    got = client.get("/api/settings").json()
    assert got["theme"] == "light"
    assert got["autoplay_next"] is False
    # persisted to disk
    import json as _json
    stored = _json.loads((tmp_path / "data" / "settings.json").read_text())
    assert stored["theme"] == "light"


def test_scan_discovers_media(client, tmp_path):
    lib = _seed_media(tmp_path)
    st = _scan(client, lib)
    s = st["summary"]
    assert s["movies"] == 2
    assert s["episodes"] == 2

    movies = client.get("/api/library/movie").json()["items"]
    titles = {m["title"] for m in movies}
    assert "The Matrix" in titles and "Inception" in titles

    shows = client.get("/api/library/tv").json()["items"]
    assert any(sh["title"] == "My Show" for sh in shows)


def test_show_episodes_and_selection(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    shows = client.get("/api/library/tv").json()["items"]
    show = next(sh for sh in shows if sh["title"] == "My Show")
    detail = client.get(f"/api/shows/{show['id']}").json()
    eps = detail["episodes"]
    assert len(eps) == 2
    e1 = next(e for e in eps if e["number"] == 1)
    assert e1["file_path"].endswith("S01E01.mkv")  # correct episode file
    ep = client.get(f"/api/episodes/{e1['id']}").json()
    assert ep["season"] == 1 and ep["number"] == 1


def test_favorites_watchlist_persist(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    mid = client.get("/api/library/movie").json()["items"][0]["id"]

    assert client.post(f"/api/favorites/{mid}").json()["favorited"] is True
    fav_ids = client.get("/api/favorites").json()["ids"]
    assert mid in fav_ids
    client.delete(f"/api/favorites/{mid}")
    assert mid not in client.get("/api/favorites").json()["ids"]

    assert client.post(f"/api/watchlist/{mid}").json()["in_watchlist"] is True
    assert mid in client.get("/api/watchlist").json()["ids"]


def test_playback_progress_and_resume(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    item = client.get("/api/library/movie").json()["items"][0]
    key = f"m:{item['id']}"

    client.post("/api/playback/start", json={"media_key": key, "title": item["title"],
                                             "file_path": item["file_path"], "duration_s": 120,
                                             "media_id": item["id"]})
    # tick is throttled to 5s of wall-clock; force persistence via stop instead.
    client.post("/api/playback/stop", json={"position_s": 60, "duration_s": 120})
    prog = client.get(f"/api/playback/{key}").json()["progress"]
    assert prog is not None and prog["position_s"] == 60

    # continue-watching reflects in-progress items
    cw = client.get("/api/continue-watching").json()["items"]
    assert any(c["media_key"] == key for c in cw)


def test_history_and_finish(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    item = client.get("/api/library/movie").json()["items"][0]
    key = f"m:{item['id']}"
    client.post("/api/playback/start", json={"media_key": key, "title": item["title"],
                                             "file_path": item["file_path"], "duration_s": 100,
                                             "media_id": item["id"]})
    r = client.post("/api/playback/finish").json()
    assert r["ok"] is True
    hist = client.get("/api/history").json()["entries"]
    assert any(h["media_key"] == key for h in hist)


def test_episode_autoplay_next(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    shows = client.get("/api/library/tv").json()["items"]
    show = next(sh for sh in shows if sh["title"] == "My Show")
    eps = client.get(f"/api/shows/{show['id']}").json()["episodes"]
    e1 = next(e for e in eps if e["number"] == 1)
    client.post("/api/playback/start", json={
        "media_key": f"e:{e1['id']}", "title": show["title"], "file_path": e1["file_path"],
        "duration_s": 60, "episode_id": e1["id"], "show_id": show["id"],
        "season": 1, "number": 1})
    r = client.post("/api/playback/finish").json()
    nxt = r["next_payload"]
    assert nxt is not None and nxt["number"] == 2  # autoplay next episode


def test_search(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    r = client.get("/api/search", params={"q": "matrix"}).json()
    assert any(x["title"] == "The Matrix" for x in r["results"])
    none = client.get("/api/search", params={"q": "zzzznotfound"}).json()
    assert none["total"] == 0


def test_statistics_and_recommendations(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    stats = client.get("/api/statistics").json()
    assert stats["library"]["movie"] == 2
    reco = client.get("/api/recommendations").json()
    assert isinstance(reco["items"], list)


def test_services_registry(client):
    svcs = client.get("/api/services").json()["services"]
    keys = {s["key"] for s in svcs}
    assert {"youtube", "telegram", "spotify", "tvtime"} <= keys


def test_bookmarks(client):
    client.post("/api/bookmarks", params={"name": "DDG", "url": "https://duckduckgo.com"})
    bms = client.get("/api/bookmarks").json()["bookmarks"]
    assert any(b["url"] == "https://duckduckgo.com" for b in bms)


def test_scan_status_shape(client, tmp_path):
    lib = _seed_media(tmp_path)
    _scan(client, lib)
    st = client.get("/api/scan/status").json()
    assert "running" in st and "summary" in st and "discovered" in st
