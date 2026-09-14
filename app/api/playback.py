from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_session_local
from app.database.repositories.media import MediaRepository
from app.config import get_settings

router = APIRouter()

def get_db():
    s = get_settings()
    db = get_session_local(s.db_path)()
    try:
        yield db
    finally:
        db.close()

@router.get("/playback/{media_id}")
def get_playback(media_id: int, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    item = repo.get_by_id(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    
    progress = None
    if item.watch_progress:
        progress = {
            "position": item.watch_progress.position,
            "duration": item.watch_progress.duration,
            "completed": item.watch_progress.completed
        }
    
    return {
        "media_id": media_id,
        "title": item.title,
        "progress": progress,
        "files": [{
            "id": f.id,
            "file_path": f.file_path,
            "file_name": f.file_name
        } for f in item.files]
    }

@router.post("/playback/{media_id}/start")
def start_playback(media_id: int, data: dict = {}, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    item = repo.get_by_id(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    
    return {
        "status": "started",
        "backend": data.get("backend", "mpv"),
        "media_id": media_id
    }

@router.post("/playback/{media_id}/stop")
def stop_playback(media_id: int, data: dict = {}, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    repo.update_progress(
        media_id,
        data.get("position", 0),
        data.get("duration", 0),
        data.get("completed", False)
    )
    return {"status": "stopped"}

@router.post("/playback/{media_id}/progress")
def update_progress(media_id: int, data: dict, db: Session = Depends(get_db)):
    repo = MediaRepository(db)
    repo.update_progress(
        media_id,
        data.get("position", 0),
        data.get("duration", 0),
        data.get("completed", False)
    )
    return {"status": "updated"}
