"""Recommendations endpoint (local engine)."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/recommendations")
def recommendations(request: Request, limit: int = Query(12, ge=1, le=50)) -> dict:
    services = request.app.state.context.services
    return {"items": services.recommendations.recommended(
        services.profile.id, limit
    )}
