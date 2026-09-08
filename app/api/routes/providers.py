"""Metadata provider configuration endpoints.

The provider catalog is built from the *actual* ProviderManager instances
(never a hand-written list), so the Settings UI can only ever show providers
that really exist in this build, with their real configuration state.

Security rules enforced here:
- the full API key is NEVER returned by any endpoint — only a masked form;
- keys are persisted via SecretsStore (0600 file outside the repo);
- the response of a key update is the masked state, not the value.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Body, HTTPException, Request

from app.config.secrets import ENV_VARS

router = APIRouter()

# query strings leaked into exception messages must never carry a key
_KEY_IN_URL = re.compile(r"(api_?key=)[^&)\s\"]+", re.IGNORECASE)


def _sanitize(detail: str) -> str:
    return _KEY_IN_URL.sub(r"\1***", str(detail))


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "•••"
    return f"{value[:3]}…{value[-2:]}"


def _capability_label(capabilities: set[str]) -> str:
    labels = {
        "movie": "movies",
        "tv": "TV shows",
        "person": "people",
        "artist": "artists",
        "album": "albums",
        "artwork": "artwork",
    }
    return ", ".join(labels.get(c, c) for c in sorted(capabilities))


def _provider_dict(provider, secrets, key_env_source: bool) -> dict:
    stored = secrets.get(provider.id)
    health = provider.health()
    env_var = ENV_VARS.get(provider.id, "")
    return {
        "id": provider.id,
        "name": provider.display_name,
        "website": provider.website,
        "supplies": provider.supplies,
        "used_for": _capability_label(provider.capabilities),
        "requires_key": provider.requires_key,
        "optional_key": provider.id in ("theaudiodb",),  # free community key works
        "configured": provider.is_configured(),
        "key_masked": _mask(stored),
        "key_source": "environment" if (key_env_source and stored) else ("settings" if stored else ""),
        "env_var": env_var,
        "testable": provider.id != "tvtime",
        "health": {
            "in_cooldown": health.get("cooldown", False),
            "consecutive_failures": health.get("consecutive_failures", 0),
            "last_error": health.get("last_error", ""),
        },
    }


@router.get("/providers")
def list_providers(request: Request) -> dict:
    services = request.app.state.context.services
    manager = services.metadata.manager
    items = []
    for provider in manager.providers.values():
        env_set = bool(services.secrets.env_value(provider.id))
        items.append(_provider_dict(provider, services.secrets, env_set))
    items.sort(key=lambda p: (not p["requires_key"] or p["configured"], p["name"].lower()))
    return {
        "items": items,
        "movie_tv_chain": [p for p in manager.priority if p in manager.providers],
        "music_chain": [p for p in manager.music_priority if p in manager.providers],
        "note": (
            "Movies/TV/people are queried in chain order until one answers; "
            "music uses the music chain. Providers without an API key are "
            "skipped honestly — local file metadata is always kept."
        ),
    }


@router.put("/providers/{provider_id}/key")
def set_provider_key(request: Request, provider_id: str, body: dict = Body(...)) -> dict:
    services = request.app.state.context.services
    manager = services.metadata.manager
    provider = manager.providers.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="unknown provider")
    if provider.id == "tvtime":
        raise HTTPException(status_code=400, detail="TV Time has no public API — nothing to configure")
    value = str((body or {}).get("key", "") or "").strip()
    env_var = ENV_VARS.get(provider_id, "")
    if env_var and services.secrets.env_value(provider_id):
        raise HTTPException(
            status_code=409,
            detail=f"{env_var} is set in your environment and takes precedence; "
                   "unset it to configure the key here instead",
        )
    services.secrets.set(provider_id, value)
    # keep the live instance in sync so the next enrich run uses the new key
    provider.api_key = value
    provider.record_success()  # reset failure/cooldown state on explicit config
    stored = services.secrets.get(provider_id)
    return {
        "ok": True,
        "provider": provider_id,
        "configured": provider.is_configured(),
        "key_masked": _mask(stored),
        "message": "Key saved (0600, outside the repository)" if value else "Key removed",
    }


@router.post("/providers/{provider_id}/test")
def test_provider(request: Request, provider_id: str, body: dict = None) -> dict:
    """Run the provider's REAL probe. Optional body {"key": …} tests a
    candidate key without saving it; otherwise the configured key is used."""
    services = request.app.state.context.services
    manager = services.metadata.manager
    provider = manager.providers.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="unknown provider")
    candidate = str((body or {}).get("key", "") or "").strip()
    key_used = candidate or services.secrets.get(provider_id)
    if provider.requires_key and not key_used:
        return {
            "ok": False,
            "provider": provider_id,
            "detail": "no API key configured — enter one first",
            "tested_with": "none",
        }
    result = provider.test_connection(candidate)
    detail = _sanitize(result.get("detail", ""))
    # a raw exception string could embed the key in a URL — belt and braces
    if key_used and key_used in detail:
        detail = detail.replace(key_used, "***")
    return {
        "ok": bool(result.get("ok")),
        "provider": provider_id,
        "detail": detail,
        "tested_with": "candidate" if candidate else (
            "none" if provider_id == "tvtime" else "configured key"
        ),
    }
