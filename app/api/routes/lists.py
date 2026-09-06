"""User lists: favorites, watchlist, collections, history, continue watching."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/favorites")
def favorites(request: Request, media_type: str | None = None) -> dict:
    services = request.app.state.context.services
    return {"items": services.repos.lists.favorites(services.profile.id, media_type)}


@router.post("/favorites")
def add_favorite(request: Request, body: dict) -> dict:
    services = request.app.state.context.services
    media_type = body.get("media_type")
    media_id = body.get("media_id")
    if not media_type or not media_id:
        raise HTTPException(status_code=400, detail="media_type and media_id required")
    services.repos.lists.set_favorite(
        services.profile.id, media_type, int(media_id), True
    )
    return {"ok": True}


@router.delete("/favorites/{media_id}")
def remove_favorite(
    request: Request, media_id: int, media_type: str = Query(...)
) -> dict:
    services = request.app.state.context.services
    services.repos.lists.set_favorite(services.profile.id, media_type, media_id, False)
    return {"ok": True}


@router.get("/watchlist")
def watchlist(request: Request, media_type: str | None = None) -> dict:
    services = request.app.state.context.services
    return {"items": services.repos.lists.watchlist(services.profile.id, media_type)}


@router.post("/watchlist")
def add_watchlist(request: Request, body: dict) -> dict:
    services = request.app.state.context.services
    media_type = body.get("media_type")
    media_id = body.get("media_id")
    if not media_type or not media_id:
        raise HTTPException(status_code=400, detail="media_type and media_id required")
    services.repos.lists.set_watchlist(
        services.profile.id, media_type, int(media_id), True
    )
    return {"ok": True}


@router.delete("/watchlist/{media_id}")
def remove_watchlist(
    request: Request, media_id: int, media_type: str = Query(...)
) -> dict:
    services = request.app.state.context.services
    services.repos.lists.set_watchlist(services.profile.id, media_type, media_id, False)
    return {"ok": True}


@router.get("/history")
def history(request: Request, limit: int = 100, offset: int = 0) -> dict:
    services = request.app.state.context.services
    items = services.playback.history.list(
        services.profile.id, limit=limit, offset=offset
    )
    total = services.repos.playback.history_count(services.profile.id)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/continue-watching")
def continue_watching(request: Request, limit: int = 20) -> dict:
    services = request.app.state.context.services
    return {"items": services.playback.resume.continue_watching(
        services.profile.id, limit
    )}


# -- collections -----------------------------------------------------------------

@router.get("/collections")
def collections(request: Request) -> dict:
    services = request.app.state.context.services
    return {"items": services.collections.list()}


@router.post("/collections")
def create_collection(request: Request, body: dict) -> dict:
    services = request.app.state.context.services
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    try:
        collection = services.collections.create(name, body.get("description", "") or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": collection.id, "name": collection.name}


@router.get("/collections/{collection_id}")
def collection_items(request: Request, collection_id: int) -> dict:
    services = request.app.state.context.services
    meta = services.repos.collections.get(collection_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="collection not found")
    return {
        "id": meta.id,
        "name": meta.name,
        "description": meta.description or "",
        "items": services.collections.items(collection_id),
    }


@router.patch("/collections/{collection_id}")
def rename_collection(request: Request, collection_id: int, body: dict) -> dict:
    services = request.app.state.context.services
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    services.collections.rename(collection_id, name, body.get("description"))
    return {"ok": True}


@router.delete("/collections/{collection_id}")
def delete_collection(request: Request, collection_id: int) -> dict:
    services = request.app.state.context.services
    services.collections.delete(collection_id)
    return {"ok": True}


@router.post("/collections/{collection_id}/items")
def add_collection_item(request: Request, collection_id: int, body: dict) -> dict:
    services = request.app.state.context.services
    media_type = body.get("media_type")
    media_id = body.get("media_id")
    if not media_type or not media_id:
        raise HTTPException(status_code=400, detail="media_type and media_id required")
    services.collections.add(collection_id, media_type, int(media_id))
    return {"ok": True}


@router.delete("/collections/{collection_id}/items")
def remove_collection_item(
    request: Request,
    collection_id: int,
    media_type: str = Query(...),
    media_id: int = Query(...),
) -> dict:
    services = request.app.state.context.services
    services.collections.remove(collection_id, media_type, media_id)
    return {"ok": True}


@router.put("/collections/{collection_id}/items")
def reorder_collection_items(request: Request, collection_id: int, body: dict) -> dict:
    services = request.app.state.context.services
    order = body.get("order") or []
    services.collections.reorder(
        collection_id, [(entry[0], int(entry[1])) for entry in order]
    )
    return {"ok": True}
