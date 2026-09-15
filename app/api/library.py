from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.connection import get_session_local
from app.database.repositories.library import LibraryRepository
from app.database.repositories.media import MediaRepository
from app.database.models import Library, MediaType, MediaItem, MediaStatus, MediaFile
from app.config import get_settings
from app.scanner.scanner import scan_directory
from app.logging import get_logger
from datetime import datetime
import asyncio

router = APIRouter()
logger = get_logger("api.library")

scan_state = {
    "active": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "files_found": 0,
    "media_added": 0,
    "errors": 0,
    "cancelled": False
}

def get_db():
    s = get_settings()
    db = get_session_local(s.db_path)()
    try:
        yield db
    finally:
        db.close()

@router.get("/library")
def list_libraries(db: Session = Depends(get_db)):
    repo = LibraryRepository(db)
    libs = repo.get_all()
    return {
        "libraries": [{
            "id": lib.id,
            "name": lib.name,
            "media_type": lib.media_type.value if lib.media_type else "movie",
            "path": lib.path,
            "scan_status": lib.scan_status,
            "last_scan_at": lib.last_scan_at.isoformat() if lib.last_scan_at else None,
            "media_count": len(lib.media_items)
        } for lib in libs]
    }

@router.post("/library")
def create_library(data: dict, db: Session = Depends(get_db)):
    repo = LibraryRepository(db)
    existing = repo.find_by_path(data.get("path", ""))
    if existing:
        raise HTTPException(status_code=409, detail=f"Location already exists: {existing.path}")
    lib = repo.create(
        name=data.get("name", "New Library"),
        path=data.get("path", ""),
        media_type=data.get("media_type", "movie")
    )
    if not lib:
        raise HTTPException(status_code=409, detail="A library with this path already exists")
    return {"id": lib.id, "name": lib.name, "path": lib.path, "media_type": lib.media_type.value}

@router.delete("/library/{library_id}")
def delete_library(library_id: int, db: Session = Depends(get_db)):
    repo = LibraryRepository(db)
    repo.delete(library_id)
    return {"status": "deleted", "id": library_id}

@router.post("/library/{library_id}/scan")
def scan_library(library_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    if scan_state["active"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    
    repo = LibraryRepository(db)
    lib = repo.get_by_id(library_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    
    background.add_task(run_scan, library_id, lib.path, lib.media_type.value)
    return {"status": "scan_started", "library_id": library_id}

@router.get("/library/scan-status")
def get_scan_status():
    return scan_state

@router.post("/library/scan-cancel")
def cancel_scan():
    scan_state["cancelled"] = True
    return {"status": "cancelling"}

def run_scan(library_id: int, path: str, media_type: str):
    global scan_state
    
    scan_state = {
        "active": True, "progress": 0, "total": 0, "current_file": "",
        "files_found": 0, "media_added": 0, "errors": 0, "cancelled": False
    }
    
    s = get_settings()
    db = get_session_local(s.db_path)()
    
    try:
        lib_repo = LibraryRepository(db)
        media_repo = MediaRepository(db)
        
        lib_repo.update_scan_status(library_id, "scanning")
        logger.info(f"Starting scan of library {library_id}: {path}")
        
        def progress_callback(processed, total, current_file):
            scan_state["progress"] = processed
            scan_state["total"] = total
            scan_state["current_file"] = current_file
        
        def cancel_callback():
            return scan_state["cancelled"]
        
        files = scan_directory(path, progress_callback, cancel_callback)
        scan_state["files_found"] = len(files)
        
        for file_info in files:
            if scan_state["cancelled"]:
                break
            
            try:
                existing = db.query(MediaItem).join(MediaItem.files).filter(
                    MediaFile.file_path == file_info["file_path"]
                ).first()
                
                if existing:
                    new_media_type = MediaType(file_info["media_type"])

                    if existing.media_type != new_media_type:
                        logger.info(
                            f"Updating media type for {file_info['file_path']}: "
                            f"{existing.media_type.value} -> {new_media_type.value}"
                        )
                        existing.media_type = new_media_type
                        media_repo.update(existing)

                    continue
                
                item = MediaItem(
                    library_id=library_id,
                    media_type=MediaType(file_info["media_type"]),
                    title=file_info["file_name"].rsplit('.', 1)[0],
                    status=MediaStatus.AVAILABLE,
                    scanned_at=datetime.utcnow()
                )
                item = media_repo.create(item)
                
                media_repo.add_file(
                    media_item_id=item.id,
                    file_path=file_info["file_path"],
                    file_name=file_info["file_name"],
                    file_size=file_info["file_size"],
                    file_format=file_info["file_format"]
                )
                
                scan_state["media_added"] += 1
                
            except Exception as e:
                scan_state["errors"] += 1
                logger.error(f"Error adding {file_info['file_path']}: {e}")
        
        lib_repo.update_scan_status(library_id, "completed")
        scan_state["active"] = False
        logger.info(f"Scan complete: {scan_state['media_added']} items added")
        
    except Exception as e:
        logger.error(f"Scan error: {e}")
        scan_state["active"] = False
        lib_repo.update_scan_status(library_id, "error")
    finally:
        db.close()
