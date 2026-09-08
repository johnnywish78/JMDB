"""Regression: service availability must resolve FOR THE ASKING FRONTEND.

Proves the architectural mismatch: /api/services used to compute "embedded"
from PyQt6-WebEngine availability, so the Electron desktop app (whose Browser
Hub never touches PyQt) was told "Embedded browser unavailable" and services
opened externally instead of in the Browser Hub.
"""
from __future__ import annotations

import pytest

from app.bootstrap.dependencies import Dependencies

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


def _services(client, frontend=None):
    headers = {}
    if frontend:
        headers["X-JMDB-Frontend"] = frontend
    return {
        s["id"]: s for s in client.get("/api/services", headers=headers).json()["items"]
    }


def test_electron_frontend_gets_embedded_true(client):
    services = _services(client, "electron")
    assert set(services) == {"youtube", "telegram", "spotify", "tv_time"}
    for service in services.values():
        assert service["embedded"] is True
        # the PyQt6-WebEngine note must be gone for the Electron client
        assert "PyQt6-WebEngine" not in service["notes"]


def test_web_frontend_gets_honest_false(client):
    services = _services(client, "web")
    for service in services.values():
        assert service["embedded"] is False
        assert "Browser Hub is part of the JMDB desktop app" in service["notes"]


def test_default_without_header_is_web(client):
    services = _services(client)
    assert services["youtube"]["embedded"] is False


def test_qt_frontend_uses_real_webengine_check(client, monkeypatch):
    import app.browser.engine as engine

    monkeypatch.setattr(engine, "webengine_available", lambda: (False, "PyQt6-WebEngine not available: test"))
    import app.services.service_manager as sm

    # the manager imports the symbol directly — patch where it lives for it
    monkeypatch.setattr(sm, "webengine_available", lambda: (False, "PyQt6-WebEngine not available: test"))
    services = _services(client, "qt")
    assert services["youtube"]["embedded"] is False
    assert "PyQt6-WebEngine not available" in services["youtube"]["notes"]


def test_unknown_frontend_falls_back_to_web(client):
    services = _services(client, "smart-tv")
    assert services["youtube"]["embedded"] is False


def test_service_catalog_is_exactly_the_four(client):
    services = _services(client, "electron")
    assert set(services) == {"youtube", "telegram", "spotify", "tv_time"}
    assert services["youtube"]["url"].startswith("https://www.youtube.com")
    assert services["telegram"]["url"].startswith("https://web.telegram")
    assert services["spotify"]["url"].startswith("https://open.spotify.com")
    assert services["tv_time"]["url"].startswith("https://www.tvtime.com")
