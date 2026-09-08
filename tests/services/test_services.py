"""Tests for services registry — exactly four final services."""
from __future__ import annotations

import pytest


@pytest.fixture()
def settings(tmp_path):
    from app.config.settings import Settings
    return Settings(tmp_path / "settings.json")


def test_exactly_four_services(settings):
    from app.services.service_manager import ServiceManager
    mgr = ServiceManager(settings)
    svcs = mgr.services()
    assert len(svcs) == 4


def test_final_services_are_correct(settings):
    from app.services.service_manager import final_services
    svcs = final_services(settings)
    keys = [s.key for s in svcs]
    assert keys == ["youtube", "telegram", "spotify", "tvtime"]
    names = [s.name for s in svcs]
    assert "YouTube" in names
    assert "Telegram" in names
    assert "Spotify" in names
    assert "TV Time" in names


def test_service_urls_are_https(settings):
    from app.services.service_manager import final_services
    for svc in final_services(settings):
        assert svc.url.startswith("https://")


def test_get_returns_none_for_unknown(settings):
    from app.services.service_manager import ServiceManager
    mgr = ServiceManager(settings)
    assert mgr.get("nonexistent") is None


def test_get_returns_service(settings):
    from app.services.service_manager import ServiceManager
    mgr = ServiceManager(settings)
    yt = mgr.get("youtube")
    assert yt is not None
    assert yt.name == "YouTube"
    assert yt.url == "https://www.youtube.com"
