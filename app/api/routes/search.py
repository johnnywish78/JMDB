"""Search endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.search.filters import ALL_TYPES, SearchFilter

router = APIRouter()


@router.get("/search")
def search(
    request: Request,
    q: str = Query(""),
    types: str = Query(""),
    genre: str = "",
    year_from: int | None = None,
    year_to: int | None = None,
    min_rating: float | None = None,
    unwatched_only: bool = False,
    favorites_only: bool = False,
    limit_per_type: int = Query(20, ge=1, le=50),
) -> dict:
    if not q.strip():
        return {"query": q, "results": {}, "total": 0}
    services = request.app.state.context.services
    selected = None
    if types:
        wanted = {t.strip() for t in types.split(",") if t.strip() in ALL_TYPES}
        if wanted:
            selected = wanted
    filters = SearchFilter(
        types=selected or set(ALL_TYPES),
        genre=genre,
        year_from=year_from,
        year_to=year_to,
        min_rating=min_rating,
        unwatched_only=unwatched_only,
        favorites_only=favorites_only,
    )
    results = services.search.search(
        q, filters, services.profile.id, limit_per_type=limit_per_type
    )
    return {
        "query": q,
        "results": results,
        "total": sum(len(rows) for rows in results.values()),
    }


@router.get("/search/suggest")
def suggest(request: Request, q: str = Query(""), limit: int = 8) -> dict:
    services = request.app.state.context.services
    if not q.strip():
        return {"suggestions": []}
    return {"suggestions": services.search.suggest(q, limit)}
