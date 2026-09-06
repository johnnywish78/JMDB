"""Statistics endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/statistics")
def statistics(request: Request) -> dict:
    services = request.app.state.context.services
    profile = services.profile.id
    return {
        "overview": services.statistics.overview(profile),
        "top_genres": services.statistics.top_genres(10),
        "top_actors": services.statistics.top_people("actor", 10),
        "top_directors": services.statistics.top_people("director", 10),
        "watch_time_by_month": services.statistics.watch_time_by_month(profile, 12),
    }
