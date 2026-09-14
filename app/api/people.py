from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_session_local
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

@router.get("/people")
def list_people(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    repo = PeopleRepository(db)
    people = repo.get_all(limit, offset)
    return {
        "people": [{
            "id": p.id,
            "name": p.name,
            "biography": p.biography[:200] if p.biography else "",
            "profile_path": p.profile_path
        } for p in people]
    }

@router.get("/people/{person_id}")
def get_person(person_id: int, db: Session = Depends(get_db)):
    repo = PeopleRepository(db)
    person = repo.get_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    credits = repo.get_media_credits(person_id)
    
    return {
        "id": person.id,
        "name": person.name,
        "biography": person.biography,
        "profile_path": person.profile_path,
        "credits": [{
            "id": m.id,
            "title": m.title,
            "media_type": m.media_type.value if m.media_type else "movie"
        } for m in credits]
    }
