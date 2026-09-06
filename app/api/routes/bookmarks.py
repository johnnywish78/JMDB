"""Bookmarks endpoints (reuse the existing repository)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/bookmarks")
def bookmarks(request: Request, folder: str | None = None) -> dict:
    services = request.app.state.context.services
    items = [asdict(bm) for bm in services.bookmarks.all(folder)]
    return {"items": items}


@router.post("/bookmarks")
def add_bookmark(request: Request, body: dict) -> dict:
    services = request.app.state.context.services
    url = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    bookmark = services.bookmarks.add(
        url, body.get("title", "") or "", body.get("folder", "") or ""
    )
    return asdict(bookmark)


@router.delete("/bookmarks/{bookmark_id}")
def remove_bookmark(
    request: Request, bookmark_id: int, url: str = Query(default="")
) -> dict:
    services = request.app.state.context.services
    target = url
    if not target:
        for bookmark in services.bookmarks.all():
            if bookmark.id == bookmark_id:
                target = bookmark.url
                break
    if not target:
        raise HTTPException(status_code=404, detail="bookmark not found")
    services.bookmarks.remove(target)
    return {"ok": True}
