"""Regression: the launcher must hand the backend token to Electron.

Proves the Electron boot failure fixed in "Fix Electron backend token handoff":

run.py owns the backend (it generates the token and builds the app with it),
so when it attaches Electron via ``JMDB_BACKEND_URL`` it must also pass the
exact same token via ``JMDB_BACKEND_TOKEN``. Without it, Electron's
``BackendProcess`` attach mode yields ``token = ""`` and the window boots
``/app/boot?token=`` → 401 {"detail": "unauthorized"}.

These tests are behavioral: they drive the real ``run.py`` functions with
fakes (no source-text grepping, no real Electron, no real network) and never
print the token values.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run as launcher  # noqa: E402  (repo-root module, path set above)


# ---------------------------------------------------------------- fakes
class _FakeProcess:
    """Stands in for the subprocess.Popen object _run_electron waits on."""

    returncode = 0

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


class _FakeHealthResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ---------------------------------------------------------------- helpers
def _install_fake_electron(tmp_path, monkeypatch):
    """Point the launcher at a fake electron binary and record its launch."""
    electron_dir = tmp_path / "electron"
    bin_dir = electron_dir / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    electron_bin = bin_dir / "electron"
    electron_bin.write_text("#!/bin/sh\nexit 0\n")
    electron_bin.chmod(0o755)

    monkeypatch.setattr(launcher, "ELECTRON_DIR", electron_dir)

    launches = []

    def fake_popen(args, **kwargs):
        launches.append(
            {
                "args": list(args),
                "env": dict(kwargs.get("env") or {}),
                "cwd": str(kwargs.get("cwd") or ""),
            }
        )
        return _FakeProcess()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    return launches


# ---------------------------------------------------------------- tests
def test_electron_receives_backend_url_and_token(tmp_path, monkeypatch):
    """_run_electron must export BOTH the URL and the token to Electron."""
    launches = _install_fake_electron(tmp_path, monkeypatch)

    code = launcher._run_electron(8799, "unit-test-token-value")

    assert code == 0
    assert len(launches) == 1
    env = launches[0]["env"]
    assert env["JMDB_BACKEND_URL"] == "http://127.0.0.1:8799"
    # the exact token the caller generated for this backend, via env
    assert env["JMDB_BACKEND_TOKEN"] == "unit-test-token-value"
    assert launches[0]["args"][0].endswith("electron")
    assert launches[0]["cwd"] == str(launcher.ELECTRON_DIR)
    # the token must not leak into argv (it belongs in the environment)
    assert not any("unit-test-token-value" in part for part in launches[0]["args"])


def test_run_backend_returns_the_token_it_generated(monkeypatch):
    """_run_backend must return the very token it handed to create_app."""
    from app.api import auth as auth_module
    from app.api import server as server_module

    generated = "backend-generated-token-value"
    captured = {}

    monkeypatch.setattr(auth_module, "generate_token", lambda: generated)

    def fake_create_app(*, token=None, **kwargs):
        captured["token"] = token
        return object()

    monkeypatch.setattr(server_module, "create_app", fake_create_app)

    import uvicorn

    class FakeServer:
        def __init__(self, config):
            self.config = config

        def run(self):
            pass

    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    monkeypatch.setattr(uvicorn, "Config", lambda *args, **kwargs: object())

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: _FakeHealthResponse())

    result = launcher._run_backend()
    assert isinstance(result, tuple) and len(result) == 3, (
        "_run_backend must return (port, server, token)"
    )
    port, server, token = result
    assert token == generated          # the returned token is the generated one
    assert captured["token"] == generated  # ...and it is the one the app runs with
    assert isinstance(server, FakeServer)
    assert isinstance(port, int)


def test_main_wires_backend_token_to_electron(monkeypatch):
    """main() must forward the backend's token into _run_electron."""
    monkeypatch.setattr(launcher.sys, "argv", ["run.py"])
    monkeypatch.setattr(
        launcher, "_run_backend", lambda: (8799, type("Server", (), {})(), "main-flow-token")
    )

    received = {}

    def fake_run_electron(backend_port, backend_token):
        received["port"] = backend_port
        received["token"] = backend_token
        return 0

    monkeypatch.setattr(launcher, "_run_electron", fake_run_electron)

    code = launcher.main()

    assert code == 0
    assert received["port"] == 8799
    assert received["token"] == "main-flow-token"
