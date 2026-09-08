"""Services endpoint: the registered service catalog with real availability."""
from __future__ import annotations

from fastapi import APIRouter, Header, Request

router = APIRouter()


@router.get("/services")
def services(request: Request, x_jmdb_frontend: str | None = Header(default=None)) -> dict:
    """Service catalog, availability resolved FOR THE ASKING FRONTEND.

    The renderer sends ``X-JMDB-Frontend: electron`` (see api.js); a plain
    browser gets the honest "web" answer; the legacy Qt UI may send ``qt``.
    """
    manager = request.app.state.context.services.service_manager
    frontend = (x_jmdb_frontend or "web").strip().lower()
    if frontend not in ("electron", "qt", "web"):
        frontend = "web"
    items = []
    for status in manager.statuses(frontend):
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
