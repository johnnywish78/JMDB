from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
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

def item_dict(item, full=False, db=None):
    r = {
        "id": item.id,
        "title": item.title,
        "original_title": item.original_title,
        "media_type": item.media_type.value if item.media_type else "movie",
        "description": item.description,
        "year": item.year,
        "runtime": item.runtime,
        "season_number": item.season_number,
        "episode_number": item.episode_number,
        "episode_title": item.episode_title,
        "rating": item.rating,
        "votes": item.votes,
        "favorite": item.favorite,
        "status": item.status.value if item.status else "available",
        "created_at": item.created_at.isoformat() if item.created_at else None
    }

    # Lightweight artwork for Library cards.
    # Full artwork/details remain available through item_dict(..., full=True).
    r["artwork"] = [{
        "id": a.id,
        "type": a.type,
        "url": a.url,
        "local_path": a.local_path,
        "is_primary": a.is_primary
    } for a in item.artwork]

    # People are needed by both Library/media cards and full media details.
    # The relationship itself is authoritative; db is only needed to read
    # role/character metadata from the association table.
    if item.people:
        people_by_id = {}

        if db is not None:
            people_rows = db.execute(
                text(
                    """
                    SELECT
                        person_id,
                        role,
                        character_name
                    FROM media_people
                    WHERE media_id = :media_id
                    ORDER BY id ASC
                    """
                ),
                {"media_id": item.id},
            ).mappings().all()

            people_by_id = {
                row["person_id"]: row
                for row in people_rows
            }

        r["people"] = []

        for p in item.people:
            association = people_by_id.get(p.id, {})

            profile_url = (
                f"https://image.tmdb.org/t/p/w185{p.profile_path}"
                if p.profile_path
                and not str(p.profile_path).startswith("http")
                else p.profile_path
            )

            r["people"].append({
                "id": p.id,
                "name": p.name,
                "role": association.get("role") or "actor",
                "character_name": association.get("character_name"),
                "profile_path": p.profile_path,
                "profile_url": profile_url,
                "tmdb_id": p.tmdb_id,
                "imdb_id": p.imdb_id,
                "known_for_department": p.known_for_department,
                "birthday": p.birthday,
                "deathday": p.deathday,
                "place_of_birth": p.place_of_birth,
                "popularity": p.popularity,
            })
    else:
        r["people"] = []

    # Trailer metadata is needed by Library cards as well as full details.
    # Keep it lightweight so list responses expose the same trailer data
    # without loading files/genres/watch progress.
    imdb_id = None
    imdb_url = None

    for external in item.external_ids:
        provider = str(external.provider or "").lower()
        external_id = str(external.external_id or "").strip()
        external_url = str(external.url or "").strip()

        if provider == "imdb" or external_id.startswith("tt"):
            if external_id.startswith("tt"):
                imdb_id = external_id
            elif external_url:
                import re
                match = re.search(r"(tt\d+)", external_url)
                if match:
                    imdb_id = match.group(1)

            if external_url.startswith("http"):
                imdb_url = external_url
            elif imdb_id:
                imdb_url = f"https://www.imdb.com/title/{imdb_id}/"

            if imdb_id:
                break

    r["trailer"] = {
        "key": item.trailer_key,
        "name": item.trailer_name,
        "site": item.trailer_site,
        "type": item.trailer_type,
        "official": bool(item.trailer_official),
        "imdb_id": imdb_id,
        "imdb_url": imdb_url,
        "thumbnail_url": (
            f"https://img.youtube.com/vi/{item.trailer_key}/hqdefault.jpg"
            if item.trailer_key
            and str(item.trailer_site or "").lower() == "youtube"
            else None
        ),
        "embed_url": (
            f"https://www.youtube.com/embed/{item.trailer_key}"
            if item.trailer_key
            and str(item.trailer_site or "").lower() == "youtube"
            else None
        ),
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
        "items": [item_dict(i, db=db) for i in items],
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/media/recent")
def get_recent(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    items = repo.get_recently_added(limit)
    return {"items": [item_dict(i, db=db) for i in items]}

@router.get("/media/favorites")
def get_favorites(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    items = repo.get_favorites(limit)
    return {"items": [item_dict(i, db=db) for i in items]}

@router.get("/media/continue-watching")
def get_continue_watching(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    items = repo.get_continue_watching(limit)
    return {"items": [item_dict(i, db=db) for i in items]}

@router.get("/media/search")
def search_media(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    repo = MediaRepository(db)
    items = repo.search(q, limit)
    return {"query": q, "items": [item_dict(i, db=db) for i in items], "total": len(items)}

@router.get("/media/{media_id}")
def get_media(media_id: int, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    item = repo.get_by_id(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    return item_dict(item, full=True, db=db)

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
    return item_dict(created, db=db)

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
    return item_dict(updated, db=db)

@router.post("/media/{media_id}/metadata")
async def fetch_media_metadata(
    media_id: int,
    db: Session = Depends(get_db),
):
    """Fetch and save metadata for one media item."""
    from app.metadata.fetcher import enrich_media_metadata

    repo = MediaRepository(db)
    item = repo.get_by_id(media_id)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Media not found"
        )

    if not item.files:
        raise HTTPException(
            status_code=400,
            detail="Media item has no associated file"
        )

    try:
        success = await enrich_media_metadata(
            media_item_id=item.id,
            filename=item.files[0].file_name,
            media_type=item.media_type.value,
            db_session=db,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"Metadata fetch failed: {e}"
        )

    if not success:
        raise HTTPException(
            status_code=424,
            detail=(
                "Metadata could not be fetched. "
                "Check TMDB API configuration."
            )
        )

    updated = repo.get_by_id(media_id)

    return {
        "status": "updated",
        "item": item_dict(updated, full=True),
    }


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
