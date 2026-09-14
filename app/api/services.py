from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_session_local
from app.database.repositories.services import ServicesRepository
from app.database.models import Service
from app.config import get_settings
from app.metadata.providers.tmdb import TMDBProvider
from app.metadata.providers.omdb import OMDbProvider

router = APIRouter()

DEFAULT_SERVICES = [
    {"name": "TMDB", "category": "metadata"},
    {"name": "OMDb", "category": "metadata"},
    {"name": "IMDb", "category": "metadata"},
    {"name": "YouTube", "category": "integration"},
    {"name": "Telegram", "category": "integration"},
    {"name": "Spotify", "category": "integration"},
    {"name": "TV Time", "category": "integration"}
]

def get_db():
    s = get_settings()
    db = get_session_local(s.db_path)()
    try:
        yield db
    finally:
        db.close()

@router.get("/services")
def list_services(db: Session = Depends(get_db)):
    repo = ServicesRepository(db)
    services = repo.get_all_services()
    
    if not services:
        for sd in DEFAULT_SERVICES:
            repo.create_service(Service(**sd))
        services = repo.get_all_services()
    
    return {
        "services": [{
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "enabled": s.enabled,
            "configured": s.configured,
            "health_status": s.health_status,
            "has_api_key": bool(s.api_key)
        } for s in services]
    }

@router.patch("/services/{sid}")
def update_service(sid: int, data: dict, db: Session = Depends(get_db)):
    repo = ServicesRepository(db)
    s = repo.get_service(sid)
    if not s:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if "enabled" in data:
        s.enabled = data["enabled"]
    if "api_key" in data:
        s.api_key = data["api_key"]
        s.configured = bool(data["api_key"])
    
    repo.update_service(s)
    return {"id": s.id, "enabled": s.enabled, "configured": s.configured}

@router.post("/services/{sid}/test")
def test_service(sid: int, db: Session = Depends(get_db)):
    settings = get_settings()
    repo = ServicesRepository(db)
    s = repo.get_service(sid)
    if not s:
        raise HTTPException(status_code=404, detail="Service not found")
    
    healthy = False
    
    if s.name == "TMDB":
        provider = TMDBProvider(api_key=s.api_key or settings.tmdb_api_key)
        healthy = provider.health_check()
    elif s.name == "OMDb":
        provider = OMDbProvider(api_key=s.api_key or settings.omdb_api_key)
        healthy = provider.health_check()
    else:
        healthy = s.configured
    
    repo.update_health(sid, "healthy" if healthy else "unhealthy")
    return {"service_id": sid, "healthy": healthy}
