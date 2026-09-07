"""Regression: provider API key configuration (Settings → Provider keys).

Proves the "no usable UI for API keys" bug: there was no endpoint at all.
Also locks the security contract:
- the full key is NEVER present in any response (masked only);
- keys persist via SecretsStore (0600 file outside the repo) and survive a
  fresh dependency graph;
- environment variables still take precedence over stored keys;
- Test Connection runs the provider's real probe and reports honest results;
- error details with a key in a URL are sanitized.
"""
from __future__ import annotations

import json

import pytest

from app.bootstrap.dependencies import Dependencies

from fastapi.testclient import TestClient

FAKE_KEY = "unit-test-fake-key-0123456789abcdef"


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


def test_catalog_lists_only_real_providers(client):
    data = client.get("/api/providers").json()
    ids = {p["id"] for p in data["items"]}
    # exactly the providers wired in build_services — nothing invented
    assert ids == {
        "tmdb", "omdb", "tvmaze", "itunes", "musicbrainz",
        "theaudiodb", "lastfm", "fanarttv", "tvtime",
    }
    for provider in data["items"]:
        assert provider["name"] and provider["website"]
        assert "supplies" in provider and "requires_key" in provider
        assert "key_masked" in provider
    assert data["movie_tv_chain"][0] == "tmdb"
    assert data["music_chain"][0] == "musicbrainz"


def test_key_lifecycle_set_mask_persist_clear(client, jmdb_home):
    response = client.put(f"/api/providers/tmdb/key", json={"key": FAKE_KEY})
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert FAKE_KEY not in json.dumps(body)  # masked only
    assert body["key_masked"].startswith("uni")

    # catalog never leaks it either
    catalog = json.dumps(client.get("/api/providers").json())
    assert FAKE_KEY not in catalog

    # secrets file: 0600, outside the repo
    secrets_file = jmdb_home / "config" / "secrets.json"
    assert secrets_file.exists()
    assert (secrets_file.stat().st_mode & 0o777) == 0o600

    # a fresh dependency graph on the same home still sees the key
    fresh = Dependencies()
    try:
        assert fresh.secrets.get("tmdb") == FAKE_KEY
    finally:
        fresh.close()

    # clearing works
    response = client.put("/api/providers/tmdb/key", json={"key": ""})
    assert response.json()["configured"] is False
    assert client.get("/api/providers").json()["items"][0]["key_masked"] == ""


def test_live_provider_uses_new_key_immediately(client):
    services = client.context.services
    assert services.providers["tmdb"].api_key == ""
    client.put("/api/providers/tmdb/key", json={"key": FAKE_KEY})
    assert services.providers["tmdb"].api_key == FAKE_KEY
    assert services.providers["tmdb"].is_configured() is True
    client.put("/api/providers/tmdb/key", json={"key": ""})


def test_unknown_provider_404(client):
    assert client.put("/api/providers/nope/key", json={"key": "x"}).status_code == 404
    assert client.post("/api/providers/nope/test", json={}).status_code == 404


def test_tvtime_key_rejected_honestly(client):
    response = client.put("/api/providers/tvtime/key", json={"key": "x"})
    assert response.status_code == 400
    assert "no public API" in response.json()["detail"]


def test_test_connection_honest_without_key(client):
    response = client.post("/api/providers/tmdb/test", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "no API key configured" in body["detail"]


def test_test_connection_succeeds_with_mocked_http(client, monkeypatch):
    """The probe path is the provider's REAL test_connection; only the
    network boundary is mocked (same policy as the existing provider tests)."""
    provider = client.context.services.providers["tmdb"]
    monkeypatch.setattr(
        provider.http, "get_json",
        lambda *args, **kwargs: {"images": {}},
    )
    response = client.post("/api/providers/tmdb/test", json={"key": FAKE_KEY})
    body = response.json()
    assert body["ok"] is True
    assert body["tested_with"] == "candidate"


def test_test_connection_failure_detail_is_sanitized(client, monkeypatch):
    """An exception string containing the key in a URL must come back masked."""
    provider = client.context.services.providers["tmdb"]

    def boom(*args, **kwargs):
        raise RuntimeError(
            f"request failed: https://api.themoviedb.org/3/configuration?api_key={FAKE_KEY}"
        )

    monkeypatch.setattr(provider.http, "get_json", boom)
    response = client.post("/api/providers/tmdb/test", json={"key": FAKE_KEY})
    body = response.json()
    assert body["ok"] is False
    assert FAKE_KEY not in body["detail"]
    assert "api_key=***" in body["detail"]


def test_env_var_takes_precedence_and_blocks_overwrite(client, monkeypatch):
    # simulate the key arriving via the process environment
    monkeypatch.setenv("TMDB_API_KEY", "env-value-key-123456")
    store_env = client.context.services.secrets._env
    store_env["TMDB_API_KEY"] = "env-value-key-123456"

    from app.config.secrets import SecretsStore

    store = SecretsStore(client.context.services.secrets._file.parent)
    assert store.get("tmdb") == "env-value-key-123456"
    response = client.put("/api/providers/tmdb/key", json={"key": FAKE_KEY})
    assert response.status_code == 409
    assert "TMDB_API_KEY" in response.json()["detail"]


def test_metadata_sources_transparent_on_detail(client, jmdb_home):
    """Detail endpoints expose which providers supplied the data."""
    from tests.seedlib import seed_library

    ids = seed_library(client.context.services, jmdb_home)
    # record a source exactly like the enricher does
    repos = client.context.services.repos
    repos.metadata_sources.record("movie", ids["movie_id"], "tmdb")

    detail = client.get(f"/api/movies/{ids['movie_id']}").json()
    assert detail["metadata"]["sources"] == ["tmdb"]
    assert detail["metadata"]["last_fetched"]

    # an item without provider data says so honestly (empty list)
    other = client.get(f"/api/movies/{ids['movie2_id']}").json()
    assert other["metadata"]["sources"] == []
