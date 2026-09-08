"""Regression: dependency declarations must cover the runtime.

Proves the "No supported WebSocket library detected" class of bug at its
root: requirements.txt described the old PyQt-only app and did not declare
fastapi/uvicorn/websockets at all, so a clean install could neither run the
backend nor serve WebSocket events.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _requirements() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in (REPO_ROOT / "requirements.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split(">=")[0].split("==")[0].split("<")[0].strip().lower()
        entries[name] = line
    return entries


def test_runtime_dependencies_declared():
    reqs = _requirements()
    for required in ("fastapi", "uvicorn", "websockets", "requests", "pillow", "mutagen"):
        assert required in reqs, (
            f"{required} missing from requirements.txt — a clean install "
            "must be able to run the backend"
        )


def test_websocket_support_declared():
    """uvicorn needs a websocket implementation for /ws to work at all."""
    assert "websockets" in _requirements() or "wsproto" in _requirements()


def test_pyqt6_webengine_not_a_runtime_requirement():
    """The Electron Browser Hub must not depend on PyQt6-WebEngine."""
    active = _requirements()
    assert "pyqt6-webengine" not in active
    assert "pyqt6" not in active  # legacy UI only — optional, commented out


def test_importable_with_declared_deps():
    """The backend imports with only the declared core (PyQt not needed)."""
    import subprocess
    import sys

    code = "import app.api.server, app.library.scanner, app.services.service_manager; print('ok')"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_dev_requirements_cover_tests():
    text = (REPO_ROOT / "requirements-dev.txt").read_text()
    for required in ("pytest", "httpx", "pytest-qt"):
        assert required in text.lower()
