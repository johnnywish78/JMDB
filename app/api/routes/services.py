"""Services endpoint: the registered service catalog with real availability."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/services")
def services(request: Request) -> dict:
    manager = request.app.state.context.services.service_manager
    items = []
    for status in manager.statuses():
        definition = status.definition
        items.append({
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "url": manager.configured_url(definition),
            "category": definition.category,
            "icon": definition.icon_emoji,
            "accent": definition.accent,
            "requires_drm": definition.requires_drm,
            "embedded": status.embedded_available,
            "external": status.external_available,
            "external_browser": status.external_browser,
            "notes": status.notes,
        })
    return {"items": items}
