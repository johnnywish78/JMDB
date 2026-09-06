"""Settings endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Request

from app.config.settings import SettingsError

router = APIRouter()


@router.get("/settings")
def get_settings(request: Request) -> dict:
    settings = request.app.state.context.services.settings
    from app.config.settings import DEFAULTS

    return {"values": {key: settings.get(key) for key in DEFAULTS}}


@router.patch("/settings")
def patch_settings(request: Request, values: dict = Body(...)) -> dict:
    settings = request.app.state.context.services.settings
    if "values" in values and isinstance(values["values"], dict):
        values = values["values"]
    applied = {}
    for key, value in values.items():
        try:
            settings.set(key, value)
            applied[key] = settings.get(key)
        except (SettingsError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"values": applied}


@router.get("/settings/schema")
def settings_schema(request: Request) -> dict:
    """All known keys with current values, for building the settings UI."""
    from app.config.settings import DEFAULTS

    settings = request.app.state.context.services.settings
    return {
        "defaults": dict(DEFAULTS),
        "values": {key: settings.get(key) for key in DEFAULTS},
    }
