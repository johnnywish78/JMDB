"""Media detail endpoints + list actions (favorite/watchlist/watched/rating)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

_MEDIA_ACTIONS = {
    "movie", "tv_show", "episode", "artist", "album", "track", "person",
}


def _detail_for(services, media_type: str, media_id: int, profile_id: int):
    if media_type == "movie":
        return services.movies.detail(media_id, profile_id)
    if media_type == "tv_show":
        return services.tv.show_detail(media_id, profile_id)
    if media_type == "season":
        return services.tv.season_detail(media_id, profile_id)
    if media_type == "episode":
        return services.tv.episode_detail(media_id, profile_id)
    if media_type == "person":
        return services.people.person_detail(media_id, profile_id)
    if media_type == "artist":
        return services.music.artist_detail(media_id, profile_id)
    if media_type == "album":
        return services.music.album_detail(media_id, profile_id)
    return None


def _attach_metadata_sources(services, media_type: str, media_id: int, detail: dict) -> dict:
    """Make the metadata source transparent: which providers actually
    supplied this item's data, and when it was last fetched. Local file
    metadata only → empty sources list (the UI shows "local files")."""
    if not isinstance(detail, dict):
        return detail
    try:
        recorded_type = {
            "tv_show": "tv_show",
            "movie": "movie",
            "artist": "artist",
            "album": "album",
        }.get(media_type)
        if recorded_type is None:
            # seasons/episodes/people: sources are recorded at show/artist level
            return detail
        sources = services.repos.metadata_sources.providers_for(recorded_type, media_id)
        last = services.repos.metadata_sources.last_fetched(recorded_type, media_id)
        detail["metadata"] = {
            "sources": [s for s in sources if s and s != "local"],
            "last_fetched": last or "",
        }
    except Exception:  # pragma: no cover - transparency must never break a page
        detail.setdefault("metadata", {"sources": [], "last_fetched": ""})
    return detail


@router.get("/media/{media_type}/{media_id}")
def media_detail(request: Request, media_type: str, media_id: int) -> dict:
    services = request.app.state.context.services
    detail = _detail_for(services, media_type, media_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"{media_type} {media_id} not found")
    return _attach_metadata_sources(services, media_type, media_id, detail)


@router.get("/movies/{movie_id}")
def movie_detail(request: Request, movie_id: int) -> dict:
    services = request.app.state.context.services
    detail = services.movies.detail(movie_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="movie not found")
    return _attach_metadata_sources(services, "movie", movie_id, detail)


@router.get("/shows/{show_id}")
def show_detail(request: Request, show_id: int) -> dict:
    services = request.app.state.context.services
    detail = services.tv.show_detail(show_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="show not found")
    return _attach_metadata_sources(services, "tv_show", show_id, detail)


@router.get("/seasons/{season_id}")
def season_detail(request: Request, season_id: int) -> dict:
    services = request.app.state.context.services
    detail = services.tv.season_detail(season_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="season not found")
    return detail


@router.get("/episodes/{episode_id}")
def episode_detail(request: Request, episode_id: int) -> dict:
    services = request.app.state.context.services
    detail = services.tv.episode_detail(episode_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return detail


@router.get("/music/artists/{artist_id}")
def artist_detail(request: Request, artist_id: int) -> dict:
    services = request.app.state.context.services
    detail = services.music.artist_detail(artist_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="artist not found")
    return _attach_metadata_sources(services, "artist", artist_id, detail)


@router.get("/music/albums/{album_id}")
def album_detail(request: Request, album_id: int) -> dict:
    services = request.app.state.context.services
    detail = services.music.album_detail(album_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="album not found")
    return _attach_metadata_sources(services, "album", album_id, detail)


@router.get("/people")
def list_people(
    request: Request, page: int = 0, per_page: int = 60, query: str = ""
) -> dict:
    services = request.app.state.context.services
    items, total = services.people.list_page(page=page, per_page=per_page, query=query)
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/people/{person_id}")
def person_detail(request: Request, person_id: int) -> dict:
    services = request.app.state.context.services
    detail = services.people.person_detail(person_id, services.profile.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="person not found")
    return detail


# -- list actions (shared by detail pages) ----------------------------------------

@router.post("/media/{media_type}/{media_id}/favorite")
def set_favorite(request: Request, media_type: str, media_id: int, body: dict = None) -> dict:
    services = request.app.state.context.services
    value = bool((body or {}).get("value", True))
    services.repos.lists.set_favorite(services.profile.id, media_type, media_id, value)
    return {"favorite": value}


@router.post("/media/{media_type}/{media_id}/watchlist")
def set_watchlist(request: Request, media_type: str, media_id: int, body: dict = None) -> dict:
    services = request.app.state.context.services
    value = bool((body or {}).get("value", True))
    services.repos.lists.set_watchlist(services.profile.id, media_type, media_id, value)
    return {"watchlist": value}


@router.post("/media/{media_type}/{media_id}/watched")
def set_watched(request: Request, media_type: str, media_id: int, body: dict = None) -> dict:
    services = request.app.state.context.services
    value = bool((body or {}).get("value", True))
    playback = services.playback
    if media_type == "tv_show":
        if value:
            playback.mark_show_watched(services.profile.id, media_id)
        else:
            raise HTTPException(status_code=400, detail="cannot unwatch a whole show at once")
    elif media_type == "season":
        if value:
            playback.mark_season_watched(services.profile.id, media_id)
        else:
            raise HTTPException(status_code=400, detail="cannot unwatch a whole season at once")
    elif value:
        playback.mark_watched(services.profile.id, media_type, media_id)
    else:
        playback.mark_unwatched(services.profile.id, media_type, media_id)
    return {"watched": value}


@router.post("/media/{media_type}/{media_id}/rating")
def set_rating(request: Request, media_type: str, media_id: int, body: dict = None) -> dict:
    services = request.app.state.context.services
    value = (body or {}).get("value")
    services.repos.lists.set_rating(
        services.profile.id, media_type, media_id,
        None if value is None else float(value),
    )
    return {"rating": value}


@router.post("/media/{media_type}/{media_id}/metadata/refresh")
async def refresh_metadata(request: Request, media_type: str, media_id: int) -> dict:
    """Force a metadata refresh from the configured providers (background)."""
    import asyncio

    services = request.app.state.context.services
    profile_id = services.profile.id

    if media_type == "movie":
        async def work():
            return await asyncio.to_thread(
                services.metadata.enrich_movie, media_id, True, profile_id
            )
    elif media_type == "tv_show":
        async def work():
            return await asyncio.to_thread(
                services.metadata.enrich_show, media_id, True
            )
    else:
        raise HTTPException(status_code=400, detail=f"no refresher for {media_type}")

    task = asyncio.get_event_loop().create_task(work())

    def _done(_fut) -> None:
        try:
            _ok = _fut.result()
        except Exception:
            import logging

            logging.getLogger(__name__).exception("metadata refresh failed")

    task.add_done_callback(_done)
    return {"started": True}
