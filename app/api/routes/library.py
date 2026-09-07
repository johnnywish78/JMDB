"""Library endpoints: summary, locations, and paginated catalog lists."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


def _location_dict(location) -> dict:
    return {
        "id": location.id,
        "path": location.path,
        "label": getattr(location, "label", "") or "",
        "last_scan_status": getattr(location, "last_scan_status", "") or "",
        "last_scan_at": getattr(location, "last_scan_at", "") or "",
    }


@router.get("/library")
def library_summary(request: Request) -> dict:
    services = request.app.state.context.services
    counts = services.library.location_file_counts()
    return {
        "summary": services.library.library_summary(),
        "locations": [
            dict(_location_dict(loc), file_count=counts.get(loc.id, 0))
            for loc in services.library.locations()
        ],
        "scanning": request.app.state.context.scan.running,
    }


@router.post("/library/locations", status_code=201)
def add_location(request: Request, body: dict = None) -> dict:
    services = request.app.state.context.services
    path = (body or {}).get("path", "").strip()
    label = (body or {}).get("label", "") or ""
    if not path:
        raise HTTPException(status_code=400, detail="path required")
    ok, message = services.library.add_location(path, label)
    if not ok:
        # Distinguish "already added" (409) from "not a usable folder" (400)
        # so the UI can report the real reason instead of faking success.
        status = 409 if "already" in message else 400
        raise HTTPException(status_code=status, detail=message)
    import os

    expanded = os.path.expanduser(path)
    added = services.repos.locations.get_by_path(expanded)
    counts = services.library.location_file_counts()
    return {
        "ok": True,
        "message": message,
        "added": _location_dict(added) if added else None,
        "locations": [
            dict(_location_dict(loc), file_count=counts.get(loc.id, 0))
            for loc in services.library.locations()
        ],
    }


@router.delete("/library/locations/{location_id}")
def remove_location(request: Request, location_id: int) -> dict:
    services = request.app.state.context.services
    services.library.remove_location(location_id)
    return {"ok": True}


@router.get("/library/movies")
def list_movies(
    request: Request,
    page: int = Query(0, ge=0),
    per_page: int = Query(60, ge=1, le=200),
    sort: str = "title",
    genre: str = "",
    query: str = "",
    year_from: int | None = None,
    year_to: int | None = None,
    min_rating: float | None = None,
    favorites_only: bool = False,
    watchlist_only: bool = False,
    unwatched_only: bool = False,
    watched_only: bool = False,
    collection_id: int | None = None,
) -> dict:
    services = request.app.state.context.services
    items, total = services.movies.list_page(
        services.profile.id,
        page=page,
        per_page=per_page,
        sort=sort,
        genre=genre,
        query=query,
        year_from=year_from,
        year_to=year_to,
        min_rating=min_rating,
        favorites_only=favorites_only,
        watchlist_only=watchlist_only,
        unwatched_only=unwatched_only,
        watched_only=watched_only,
        collection_id=collection_id,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/library/tv")
def list_shows(
    request: Request,
    page: int = Query(0, ge=0),
    per_page: int = Query(60, ge=1, le=200),
    sort: str = "title",
    genre: str = "",
    query: str = "",
    favorites_only: bool = False,
    unwatched_only: bool = False,
) -> dict:
    services = request.app.state.context.services
    items, total = services.tv.list_shows(
        services.profile.id,
        page=page,
        per_page=per_page,
        sort=sort,
        genre=genre,
        query=query,
        favorites_only=favorites_only,
        unwatched_only=unwatched_only,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/library/music")
def list_music(
    request: Request,
    type: str = Query("albums", pattern="^(artists|albums|tracks)$"),
    page: int = Query(0, ge=0),
    per_page: int = Query(60, ge=1, le=200),
    query: str = "",
) -> dict:
    services = request.app.state.context.services
    if type == "artists":
        items, total = services.music.list_artists(page=page, per_page=per_page, query=query)
    elif type == "albums":
        items, total = services.music.list_albums(page=page, per_page=per_page, query=query)
    else:
        items = services.music.search_tracks(query or "", limit=per_page)
        total = len(items)
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/genres")
def genres(request: Request) -> dict:
    services = request.app.state.context.services
    return {"genres": services.search.all_genres()}
