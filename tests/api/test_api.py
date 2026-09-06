"""API integration tests: real services, temp JMDB_HOME, seeded library."""
from __future__ import annotations

import pytest

from app.bootstrap.dependencies import Dependencies
from tests.seedlib import seed_library


@pytest.fixture()
def api(jmdb_home):
    from app.api.auth import generate_token
    from app.api.context import APIContext
    from app.api.server import create_app
    from fastapi.testclient import TestClient

    token = generate_token()
    context = APIContext(Dependencies(), token)
    ids = seed_library(context.services, jmdb_home)
    app = create_app(context=context, token=token, ui_dir=jmdb_home / "no-ui")
    with TestClient(app) as client:
        client.ids = ids
        client.token = token
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    context.close()


# -- system -----------------------------------------------------------------------

def test_health_open_without_token(jmdb_home):
    from app.api.auth import generate_token
    from app.api.context import APIContext
    from app.api.server import create_app
    from fastapi.testclient import TestClient

    context = APIContext(Dependencies(), generate_token())
    app = create_app(context=context)
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    context.close()


def test_unauthorized_without_token(api):
    from fastapi.testclient import TestClient  # noqa: F401

    response = api.get("/api/settings", headers={"Authorization": ""})
    assert response.status_code == 401


def test_non_local_host_rejected(api):
    response = api.get("/api/health", headers={"Host": "evil.example.com:1234"})
    assert response.status_code == 421


def test_app_info(api):
    data = api.get("/api/app/info").json()
    assert data["name"] == "JMDB"
    assert "playback_backends" in data
    assert "providers" in data


# -- settings ---------------------------------------------------------------------

def test_settings_get_patch(api):
    values = api.get("/api/settings").json()["values"]
    assert values["theme"] in ("dark", "light", "system")

    response = api.patch("/api/settings", json={"theme": "light"})
    assert response.status_code == 200
    assert response.json()["values"]["theme"] == "light"

    # invalid key rejected, nothing applied
    response = api.patch("/api/settings", json={"not_a_key": 1})
    assert response.status_code == 400

    assert api.get("/api/settings").json()["values"]["theme"] == "light"


# -- library ----------------------------------------------------------------------

def test_library_summary_and_locations(api):
    data = api.get("/api/library").json()
    assert data["summary"]["movies"] == 2
    assert data["summary"]["shows"] == 2
    assert data["summary"]["tracks"] == 2
    assert len(data["locations"]) == 3

    response = api.post(
        "/api/library/locations", json={"path": "/definitely/not/a/dir"}
    )
    assert response.status_code == 200 and response.json()["ok"] is False


def test_remove_location(api, jmdb_home):
    from tests.seedlib import seed_media_tree

    extra = jmdb_home / "extra-media"
    seed_media_tree(extra / "x")  # any dir works; validity is what matters
    ok = api.post("/api/library/locations", json={"path": str(extra / "x" / "Movies")}).json()
    assert ok["ok"] is True
    locations = api.get("/api/library").json()["locations"]
    added = [loc for loc in locations if loc["path"].endswith("extra-media/x/Movies")]
    assert added
    response = api.delete(f"/api/library/locations/{added[0]['id']}")
    assert response.status_code == 200


def test_movies_list_and_filters(api):
    data = api.get("/api/library/movies").json()
    assert data["total"] == 2
    titles = {row["title"] for row in data["items"]}
    assert "Night Runner" in titles

    data = api.get("/api/library/movies", params={"query": "night"}).json()
    assert data["total"] == 1 and data["items"][0]["title"] == "Night Runner"

    data = api.get("/api/library/movies", params={"year_from": 2020}).json()
    assert data["total"] == 1

    data = api.get("/api/library/movies", params={"query": "zzz-nothing"}).json()
    assert data["total"] == 0


def test_tv_list(api):
    data = api.get("/api/library/tv").json()
    assert data["total"] == 2
    assert {row["title"] for row in data["items"]} >= {"Solar Winds", "Desert Show"}


def test_music_lists(api):
    albums = api.get("/api/library/music", params={"type": "albums"}).json()
    assert albums["total"] == 1
    assert albums["items"][0]["title"] == "Midnight Sessions"
    artists = api.get("/api/library/music", params={"type": "artists"}).json()
    assert artists["total"] == 1


# -- details ----------------------------------------------------------------------

def test_movie_detail_and_404(api):
    data = api.get(f"/api/movies/{api.ids['movie_id']}").json()
    assert data["title"] == "Night Runner"
    assert data["is_favorite"] is True
    assert any(credit["name"] == "Dana Starfield" for credit in data["credits"])
    assert api.get("/api/movies/999999").status_code == 404


def test_show_and_season_detail(api):
    show = api.get(f"/api/shows/{api.ids['show_id']}").json()
    assert show["title"] == "Solar Winds"
    assert show["season_count"] >= 1
    season = api.get(f"/api/seasons/{api.ids['season_id']}").json()
    assert len(season["episodes"]) == 3  # multi-episode file expands
    episode = api.get(f"/api/episodes/{api.ids['episode_id']}").json()
    assert episode["show_title"] == "Solar Winds"
    assert episode["season_number"] == 1


def test_people(api):
    data = api.get("/api/people").json()
    assert data["total"] >= 2
    person = api.get(f"/api/people/{api.ids['person_id']}").json()
    assert person["name"] == "Dana Starfield"
    assert len(person.get("filmography", [])) >= 1


def test_media_generic_route(api):
    data = api.get(f"/api/media/movie/{api.ids['movie_id']}").json()
    assert data["title"] == "Night Runner"
    data = api.get(f"/api/media/album/{api.ids['album_id']}").json()
    assert data["title"] == "Midnight Sessions"


# -- home -------------------------------------------------------------------------

def test_home_bundle(api):
    data = api.get("/api/home").json()
    assert len(data["continue_watching"]) >= 1  # seeded episode position
    assert len(data["recently_added"]) == 2
    assert len(data["recent_episodes"]) >= 3
    assert len(data["favorites"]) >= 1
    assert data["stats"]["movies"] == 2
    assert isinstance(data["hero"], list)


# -- lists ------------------------------------------------------------------------

def test_favorites_flow(api):
    before = api.get("/api/favorites").json()["items"]
    assert any(item["title"] == "Night Runner" for item in before)

    api.delete(
        f"/api/favorites/{api.ids['movie_id']}", params={"media_type": "movie"}
    )
    after = api.get("/api/favorites").json()["items"]
    assert not any(item["title"] == "Night Runner" for item in after)

    api.post("/api/favorites", json={"media_type": "movie", "media_id": api.ids["movie_id"]})
    restored = api.get("/api/favorites").json()["items"]
    assert any(item["title"] == "Night Runner" for item in restored)


def test_watchlist_flow(api):
    api.delete(f"/api/watchlist/{api.ids['movie2_id']}", params={"media_type": "movie"})
    assert not api.get("/api/watchlist").json()["items"]
    api.post("/api/watchlist", json={"media_type": "movie", "media_id": api.ids["movie2_id"]})
    assert len(api.get("/api/watchlist").json()["items"]) == 1


def test_history_and_continue(api):
    history = api.get("/api/history").json()
    assert history["total"] >= 1
    continue_items = api.get("/api/continue-watching").json()["items"]
    assert any(item["title"] == "Solar.Winds.S01E01.720p" or "Solar" in item["title"]
               for item in continue_items)


def test_collections_flow(api):
    collections = api.get("/api/collections").json()["items"]
    assert any(c["name"] == "Weekend picks" for c in collections)
    collection_id = api.ids["collection_id"]

    items = api.get(f"/api/collections/{collection_id}").json()["items"]
    assert len(items) == 2

    api.delete(
        f"/api/collections/{collection_id}/items",
        params={"media_type": "movie", "media_id": api.ids["movie_id"]},
    )
    items = api.get(f"/api/collections/{collection_id}").json()["items"]
    assert len(items) == 1

    created = api.post("/api/collections", json={"name": "Late night"}).json()
    assert created["name"] == "Late night"
    api.patch(f"/api/collections/{created['id']}", json={"name": "Late night 2"})
    renamed = api.get(f"/api/collections/{created['id']}").json()
    assert renamed["name"] == "Late night 2"
    api.delete(f"/api/collections/{created['id']}")


# -- search -----------------------------------------------------------------------

def test_search(api):
    data = api.get("/api/search", params={"q": "night"}).json()
    assert data["total"] >= 1
    assert any(row["title"] == "Night Runner" for row in data["results"].get("movie", []))

    data = api.get("/api/search", params={"q": "solar"}).json()
    assert any(row["title"] == "Solar Winds" for row in data["results"].get("tv_show", []))

    data = api.get("/api/search", params={"q": ""}).json()
    assert data["total"] == 0

    data = api.get("/api/search", params={"q": "aurora"}).json()
    assert data["results"].get("artist") or data["results"].get("album")


# -- recommendations / statistics ---------------------------------------------------

def test_recommendations(api):
    data = api.get("/api/recommendations").json()
    assert isinstance(data["items"], list)


def test_statistics(api):
    data = api.get("/api/statistics").json()
    assert data["overview"]["movies"] == 2
    assert "watch_seconds" in data["overview"]
    assert isinstance(data["top_genres"], list)
    assert isinstance(data["watch_time_by_month"], list)


# -- scan -------------------------------------------------------------------------

def test_scan_status_and_run(api):
    status = api.get("/api/scan/status").json()
    assert status["running"] is False

    response = api.post("/api/scan", json={})
    assert response.status_code == 200

    # wait for the background thread to finish
    import time

    for _ in range(100):
        status = api.get("/api/scan/status").json()
        if not status["running"]:
            break
        time.sleep(0.05)
    assert status["running"] is False
    assert status["last_result"] is not None
    assert status["last_result"]["status"] == "completed"


# -- bookmarks --------------------------------------------------------------------

def test_bookmarks_flow(api):
    created = api.post(
        "/api/bookmarks", json={"url": "https://example.com", "title": "Example"}
    ).json()
    assert created["url"] == "https://example.com"

    items = api.get("/api/bookmarks").json()["items"]
    assert any(item["url"] == "https://example.com" for item in items)

    api.delete(f"/api/bookmarks/{created['id']}")
    items = api.get("/api/bookmarks").json()["items"]
    assert not any(item["url"] == "https://example.com" for item in items)


# -- services ---------------------------------------------------------------------

def test_services_exactly_four(api):
    items = api.get("/api/services").json()["items"]
    ids = {item["id"] for item in items}
    assert ids == {"youtube", "telegram", "spotify", "tv_time"}


# -- playback ---------------------------------------------------------------------

def test_playback_start_stream_progress_finish(api):
    start = api.post("/api/playback/start", json={
        "media_type": "movie", "media_id": api.ids["movie_id"],
    }).json()
    assert start["media"]["title"] == "Night Runner"
    assert start["stream_url"].startswith("/api/stream/")
    file_id = start["media"]["file"]["id"]

    # full stream
    response = api.get(start["stream_url"])
    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"

    # range request
    response = api.get(start["stream_url"], headers={"Range": "bytes=0-15"})
    assert response.status_code == 206
    assert response.headers["content-length"] == "16"
    assert len(response.content) == 16

    # out-of-range
    response = api.get(start["stream_url"], headers={"Range": "bytes=99999-100000"})
    assert response.status_code == 416

    # progress + finish → watched, no next for a movie
    api.post("/api/playback/progress", json={
        "media_type": "movie", "media_id": api.ids["movie_id"],
        "position": 500, "duration": 6400,
    })
    state = api.get(
        f"/api/playback/state/{api.ids['movie_id']}", params={"media_type": "movie"}
    ).json()
    assert state["position"] == 500

    finish = api.post("/api/playback/finish", json={
        "session_id": start["session_id"], "media_type": "movie",
        "media_id": api.ids["movie_id"], "position": 6400, "duration": 6400,
    }).json()
    assert finish["watched"] is True
    assert finish["next"] is None

    state = api.get(
        f"/api/playback/state/{api.ids['movie_id']}", params={"media_type": "movie"}
    ).json()
    assert state["watched"] is True


def test_playback_episode_next_and_subtitles(api):
    start = api.post("/api/playback/start", json={
        "media_type": "episode", "media_id": api.ids["episode_id"],
        "context": {"type": "season", "id": api.ids["season_id"]},
    }).json()
    # queue = all three episodes, current flagged
    assert len(start["queue"]) == 3
    assert start["queue"][0]["current"] is True

    # external English subtitle discovered next to the file
    assert start["subtitles"], "expected the seeded .srt to be offered"
    sub = start["subtitles"][0]
    response = api.get(sub["url"])
    assert response.status_code == 200
    assert response.text.startswith("WEBVTT")
    assert "00:00:01.000" in response.text  # SRT comma → VTT dot

    finish = api.post("/api/playback/finish", json={
        "session_id": start["session_id"], "media_type": "episode",
        "media_id": api.ids["episode_id"], "position": 1500, "duration": 1500,
    }).json()
    assert finish["next"] is not None
    assert finish["next"]["media_id"] == api.ids["episode2_id"]
    assert "S01E02" in finish["next"]["subtitle"]


def test_playback_start_unplayable_404(api):
    response = api.post("/api/playback/start", json={
        "media_type": "movie", "media_id": 999999,
    })
    assert response.status_code == 404


def test_playback_watched_toggle(api):
    api.post(
        f"/api/media/movie/{api.ids['movie_id']}/watched", json={"value": True}
    )
    state = api.get(
        f"/api/playback/state/{api.ids['movie_id']}", params={"media_type": "movie"}
    ).json()
    assert state["watched"] is True
    api.post(
        f"/api/media/movie/{api.ids['movie_id']}/watched", json={"value": False}
    )
    state = api.get(
        f"/api/playback/state/{api.ids['movie_id']}", params={"media_type": "movie"}
    ).json()
    assert state["watched"] is False


# -- artwork allowlist ------------------------------------------------------------

def test_artwork_served_and_allowlist_enforced(api, jmdb_home):
    # legit artwork: the scanned poster
    detail = api.get(f"/api/movies/{api.ids['movie_id']}").json()
    poster_path = detail.get("poster_path", "")
    if not poster_path:
        # artwork table may be empty if poster wasn't linked; use home file
        poster_path = str(
            jmdb_home / "media" / "Movies" / "Night Runner (2024)" / "poster.jpg"
        )
    response = api.get("/api/artwork", params={"path": poster_path})
    assert response.status_code == 200

    # outside every allowed root → refused
    response = api.get("/api/artwork", params={"path": "/etc/passwd"})
    assert response.status_code == 404
    response = api.get("/api/artwork", params={"path": "/etc/hostname"})
    assert response.status_code == 404


# -- websocket bridge -------------------------------------------------------------

def test_websocket_events(api):
    with api.websocket_connect(f"/ws?token={api.token}") as socket:
        from app.domain.events import ToastRequested

        api.app.state.context.services.events.publish(
            ToastRequested(message="hello from the test", level="info")
        )
        message = socket.receive_json()
        assert message["type"] == "toast"
        assert message["data"]["message"] == "hello from the test"


def test_websocket_requires_token(api):
    """An unauthenticated websocket is closed before accept (deterministic
    ASGI-level probe; TestClient's blocking receive makes this flaky)."""
    import asyncio

    async def probe(query: bytes) -> list:
        scope = {
            "type": "websocket", "asgi": {"version": "3.0"},
            "http_version": "1.1", "scheme": "ws",
            "path": "/ws", "raw_path": b"/ws", "query_string": query,
            "root_path": "", "headers": [(b"host", b"127.0.0.1")],
            "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 80),
            "subprotocols": [], "app": api.app, "state": api.app.state,
        }
        sent = []

        async def receive():
            if not sent:
                return {"type": "websocket.connect"}
            return {"type": "websocket.disconnect", "code": 1000}

        async def send(message):
            sent.append(message)

        await api.app(scope, receive, send)
        return sent

    sent = asyncio.run(probe(b""))
    assert any(m["type"] == "websocket.close" for m in sent)

    sent = asyncio.run(probe(f"token={api.token}".encode()))
    assert any(m["type"] == "websocket.accept" for m in sent)
