from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.connection import get_session_local
from app.database.repositories.media import MediaRepository
from app.database.repositories.people import PeopleRepository
from app.config import get_settings

router = APIRouter()

def get_db():
    s = get_settings()
    db = get_session_local(s.db_path)()
    try:
        yield db
    finally:
        db.close()

@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    media_repo = MediaRepository(db)
    people_repo = PeopleRepository(db)
    
    media_items = media_repo.search(q, limit)
    people = people_repo.search(q, limit)
    
    return {
        "query": q,
        "media": [{
            "id": m.id,
            "title": m.title,
            "media_type": m.media_type.value if m.media_type else "movie",
            "year": m.year
        } for m in media_items],
        "people": [{
            "id": p.id,
            "name": p.name
        } for p in people],
        "total": len(media_items) + len(people)
    }
