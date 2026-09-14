from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_session_local
from app.database.repositories.services import SettingsRepository
from app.config import get_settings

router = APIRouter()

def get_db():
    s = get_settings()
    db = get_session_local(s.db_path)()
    try:
        yield db
    finally:
        db.close()

@router.get("/settings")
def get_all_settings(db: Session = Depends(get_db)):
    repo = SettingsRepository(db)
    return {"settings": repo.get_all()}

@router.patch("/settings")
def update_settings(data: dict, db: Session = Depends(get_db)):
    repo = SettingsRepository(db)
    for key, value in data.items():
        repo.set(key, str(value))
    return {"status": "updated", "message": "Settings saved successfully"}

@router.get("/settings/metadata")
def get_metadata_settings(db: Session = Depends(get_db)):
    repo = SettingsRepository(db)
    settings = repo.get_all()
    return {
        "tmdb_api_key": settings.get("tmdb_api_key", ""),
        "omdb_api_key": settings.get("omdb_api_key", ""),
        "auto_fetch_metadata": settings.get("auto_fetch_metadata", "true") == "true"
    }

@router.patch("/settings/metadata")
def update_metadata_settings(data: dict, db: Session = Depends(get_db)):
    repo = SettingsRepository(db)
    if "tmdb_api_key" in data:
        repo.set("tmdb_api_key", data["tmdb_api_key"])
    if "omdb_api_key" in data:
        repo.set("omdb_api_key", data["omdb_api_key"])
    if "auto_fetch_metadata" in data:
        repo.set("auto_fetch_metadata", str(data["auto_fetch_metadata"]).lower())
    return {"status": "updated"}
