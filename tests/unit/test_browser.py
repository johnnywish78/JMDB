"""Tests for browser engine detection and navigation logic."""
from __future__ import annotations

import pytest


def test_engine_available():
    from app.browser.engine import engine_available
    # Must not raise; result depends on environment
    result = engine_available()
    assert isinstance(result, bool)


def test_normalize_url():
    from app.browser.engine import _normalize
    assert _normalize("") == "https://duckduckgo.com"
    assert _normalize("   ") == "https://duckduckgo.com"
    assert _normalize("youtube.com") == "https://youtube.com"
    assert _normalize("https://example.com") == "https://example.com"
    assert _normalize("http://example.com/path") == "http://example.com/path"


def test_default_url():
    from app.browser.engine import DEFAULT_URL
    assert DEFAULT_URL == "https://duckduckgo.com"


def test_engine_probe_reentrant():
    """Calling _probe_webengine multiple times returns consistent results."""
    from app.browser.engine import _probe_webengine
    ok1, err1 = _probe_webengine()
    ok2, err2 = _probe_webengine()
    assert ok1 == ok2
    assert err1 == err2
