"""Regression: scan lifecycle + live WebSocket progress.

Proves the "Scan everything shows no progress" bug class:
- a scan runs start → progress (with phases) → finished over /ws;
- double-start is rejected (no uncontrolled duplicate jobs);
- the status snapshot carries phase/files counters;
- the WS requires the token (4401/close otherwise).
"""
from __future__ import annotations

import json
import time

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
    media = jmdb_home / "media"
    seed_media_tree(media)
    services = context.services
    services.library.add_location(str(media))
    app = create_app(context=context, token=token, ui_dir=jmdb_home / "no-ui")
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        c.token = token
        c.app = app
        yield c
    context.close()


def _wait_done(client, timeout=20.0) -> dict:
    deadline = time.time() + timeout
    status = {}
    while time.time() < deadline:
        status = client.get("/api/scan/status").json()
        if not status["running"]:
            return status
        time.sleep(0.05)
    raise AssertionError(f"scan still running after {timeout}s: {status}")


def test_scan_lifecycle_with_websocket_progress(client):
    with client.websocket_connect(f"/ws?token={client.token}") as ws:
        started = client.post("/api/scan")
        assert started.status_code == 200 and started.json()["started"] is True

        events = []
        deadline = time.time() + 25
        while time.time() < deadline:
            try:
                payload = json.loads(ws.receive_text())
            except Exception:
                break
            events.append(payload)
            if payload["type"] == "scan_finished":
                break
        types = [e["type"] for e in events]

        assert "scan_started" in types
        assert "scan_progress" in types, "small libraries must still see progress"
        assert "scan_finished" in types

        finished = next(e["data"] for e in events if e["type"] == "scan_finished")
        assert finished["status"] == "completed"
        assert finished["files_seen"] >= 8  # the seeded tree has ≥8 media files

        phases = {
            e["data"].get("phase")
            for e in events
            if e["type"] == "scan_progress"
        }
        assert "indexing" in phases
        assert "matching" in phases


def test_double_start_rejected(client):
    assert client.post("/api/scan").status_code == 200
    second = client.post("/api/scan")
    assert second.status_code == 409
    assert "already running" in second.json()["detail"]
    _wait_done(client)


def test_status_snapshot_shape(client):
    status = client.get("/api/scan/status").json()
    for key in ("running", "phase", "files_seen", "files_indexed", "errors", "last_result"):
        assert key in status, f"status snapshot missing {key}"


def test_websocket_without_token_rejected(client):
    """A client with NO credentials must never reach the event stream."""
    from fastapi.testclient import TestClient

    with TestClient(client.app) as anon:
        with pytest.raises(Exception):
            with anon.websocket_connect("/ws"):
                pass


def test_scan_finished_event_is_flat_not_nested(client):
    """The renderer used to look for data.result.* — the wire payload is the
    LibraryScanFinished dataclass flattened. Lock the contract."""
    with client.websocket_connect(f"/ws?token={client.token}") as ws:
        client.post("/api/scan")
        finished = None
        deadline = time.time() + 25
        while time.time() < deadline:
            payload = json.loads(ws.receive_text())
            if payload["type"] == "scan_finished":
                finished = payload["data"]
                break
        assert finished is not None
        assert "result" not in finished
        for key in ("status", "files_indexed", "duration_seconds", "movies_added"):
            assert key in finished
