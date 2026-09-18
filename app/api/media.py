from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database.connection import get_session_local
from app.database.repositories.media import MediaRepository
from app.database.models import MediaItem, MediaType, MediaStatus
from app.config import get_settings

router = APIRouter()

def get_db():
    s = get_settings()
    db = get_session_local(s.db_path)()
    try:
        yield db
    finally:
        db.close()

def item_dict(item, full=False):
    r = {
        "id": item.id,
        "title": item.title,
        "original_title": item.original_title,
        "media_type": item.media_type.value if item.media_type else "movie",
        "description": item.description,
        "year": item.year,
        "runtime": item.runtime,
        "rating": item.rating,
        "votes": item.votes,
        "favorite": item.favorite,
        "status": item.status.value if item.status else "available",
        "created_at": item.created_at.isoformat() if item.created_at else None
    }
    
    if full:
        r["files"] = [{
            "id": f.id,
            "file_name": f.file_name,
            "file_path": f.file_path,
            "file_size": f.file_size,
            "file_format": f.file_format,
            "duration": f.duration,
            "video_codec": f.video_codec,
            "audio_codec": f.audio_codec,
            "resolution": f.resolution
        } for f in item.files]
        
        r["genres"] = [g.name for g in item.genres]
        
        r["people"] = [{
            "id": p.id,
            "name": p.name,
            "role": p.role if hasattr(p, 'role') else "actor"
        } for p in item.people]
        
        r["artwork"] = [{
            "id": a.id,
            "type": a.type,
            "url": a.url,
            "local_path": a.local_path,
            "is_primary": a.is_primary
        } for a in item.artwork]
        
        r["external_ids"] = [{
            "provider": e.provider,
            "external_id": e.external_id,
            "url": e.url
        } for e in item.external_ids]
        
        if item.watch_progress:
            r["watch_progress"] = {
                "position": item.watch_progress.position,
                "duration": item.watch_progress.duration,
                "completed": item.watch_progress.completed,
                "last_watched": item.watch_progress.last_watched.isoformat() if item.watch_progress.last_watched else None
            }
    
    return r

@router.get("/media")
def list_media(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    media_type: Optional[str] = None,
    search: Optional[str] = None,
    favorite: Optional[bool] = None,
    sort: str = Query("newest"),
    db: Session = Depends(get_db)
):
    allowed_sorts = {"newest", "oldest", "title", "rating"}
    if sort not in allowed_sorts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported sort: {sort}"
        )

    repo = MediaRepository(db)
    items = repo.get_all(
        limit=limit,
        offset=offset,
        media_type=media_type,
        search=search,
        favorite=favorite,
        sort=sort,
    )
    total = repo.count(media_type, favorite=favorite)
    
    return {
        "items": [item_dict(i) for i in items],
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/media/recent")
def get_recent(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    items = repo.get_recently_added(limit)
    return {"items": [item_dict(i) for i in items]}

@router.get("/media/favorites")
def get_favorites(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    items = repo.get_favorites(limit)
    return {"items": [item_dict(i) for i in items]}

@router.get("/media/continue-watching")
def get_continue_watching(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    items = repo.get_continue_watching(limit)
    return {"items": [item_dict(i) for i in items]}

@router.get("/media/search")
def search_media(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    repo = MediaRepository(db)
    items = repo.search(q, limit)
    return {"query": q, "items": [item_dict(i) for i in items], "total": len(items)}

@router.get("/media/{media_id}")
def get_media(media_id: int, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    item = repo.get_by_id(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    return item_dict(item, full=True)

@router.post("/media")
def create_media(data: dict, db: Session = Depends(get_db)):
    item = MediaItem(
        title=data.get("title", "Unknown"),
        media_type=MediaType(data.get("media_type", "movie")),
        description=data.get("description", ""),
        year=data.get("year"),
        original_title=data.get("original_title", ""),
        runtime=data.get("runtime"),
        rating=data.get("rating")
    )
    repo = MediaRepository(db)
    created = repo.create(item)
    return item_dict(created)

@router.patch("/media/{media_id}")
def update_media(media_id: int, data: dict, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    item = repo.get_by_id(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    
    for key, value in data.items():
        if hasattr(item, key) and key not in ("id", "created_at"):
            setattr(item, key, value)
    
    updated = repo.update(item)
    return item_dict(updated)

@router.delete("/media/{media_id}")
def delete_media(media_id: int, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    repo.delete(media_id)
    return {"status": "deleted", "id": media_id}

@router.post("/media/{media_id}/favorite")
def toggle_favorite(media_id: int, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    item = repo.get_by_id(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    
    repo.set_favorite(media_id, not item.favorite)
    return {"favorite": not item.favorite}
