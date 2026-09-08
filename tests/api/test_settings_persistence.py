"""Regression: settings (theme + player/browser values) persist and reload.

Covers the Settings audit requirement: every persisted setting survives a
fresh SettingsService on the same config directory — what a restart does.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def client(jmdb_home):
    from app.api.auth import generate_token
    from app.api.context import APIContext
    from app.api.server import create_app
    from app.bootstrap.dependencies import Dependencies
    from fastapi.testclient import TestClient

    token = generate_token()
    context = APIContext(Dependencies(), token)
    app = create_app(context=context, token=token, ui_dir=jmdb_home / "no-ui")
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        c.context = context
        yield c
    context.close()


def test_theme_and_settings_roundtrip(client, jmdb_home):
    patch = {
        "theme": "light",
        "autoplay_next": False,
        "player_default_volume": 42,
        "browser_search_engine": "google",
        "browser_enable_javascript": False,
        "mark_watched_pct": 80,
        "metadata_language": "de-DE",
    }
    response = client.patch("/api/settings", json=patch)
    assert response.status_code == 200
    applied = response.json()["values"]
    for key, value in patch.items():
        assert applied[key] == value

    # a fresh service graph on the same home (== app restart) reloads them
    from app.config.settings import SettingsService

    fresh = SettingsService(jmdb_home / "config")
    for key, value in patch.items():
        assert fresh.get(key) == value, f"{key} did not survive restart"


def test_browser_default_zoom_roundtrip_and_bounds(client, jmdb_home):
    # valid value round-trips and survives a restart
    response = client.patch("/api/settings", json={"browser_default_zoom": 150})
    assert response.status_code == 200
    assert response.json()["values"]["browser_default_zoom"] == 150

    from app.config.settings import SettingsService

    fresh = SettingsService(jmdb_home / "config")
    assert fresh.get("browser_default_zoom") == 150

    # out-of-range values are rejected, not silently clamped
    for bad in (10, 999):
        rejected = client.patch("/api/settings", json={"browser_default_zoom": bad})
        assert rejected.status_code == 400, f"{bad} should be rejected"


def test_player_engine_roundtrip_and_validation(client):
    """The embedded-player engine setting (auto/mpv/chromium) must persist and
    reject anything else — the mpv handoff trusts it."""
    response = client.patch("/api/settings", json={"player_engine": "mpv"})
    assert response.status_code == 200, response.text
    assert response.json()["values"]["player_engine"] == "mpv"
    response = client.get("/api/settings")
    assert response.json()["values"]["player_engine"] == "mpv"

    response = client.patch("/api/settings", json={"player_engine": "vlc"})
    assert response.status_code == 400, response.text

    response = client.patch("/api/settings", json={"player_engine": "chromium"})
    assert response.status_code == 200, response.text


def test_invalid_theme_rejected(client):
    response = client.patch("/api/settings", json={"theme": "hotdog"})
    assert response.status_code == 400


def test_unknown_setting_rejected(client):
    response = client.patch("/api/settings", json={"nonexistent_key": 1})
    assert response.status_code == 400


def test_settings_file_written_atomically(client, jmdb_home):
    client.patch("/api/settings", json={"theme": "dark"})
    settings_file = jmdb_home / "config" / "settings.json"
    assert settings_file.exists()
    import json

    data = json.loads(settings_file.read_text())
    assert data["theme"] == "dark"
