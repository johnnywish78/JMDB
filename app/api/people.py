from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
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
            "profile_path": p.profile_path,
            "profile_url": (
                f"https://image.tmdb.org/t/p/w185{p.profile_path}"
                if p.profile_path and not str(p.profile_path).startswith("http")
                else p.profile_path
            ),
            "tmdb_id": p.tmdb_id,
            "imdb_id": p.imdb_id,
            "known_for_department": p.known_for_department,
            "birthday": p.birthday,
            "deathday": p.deathday,
            "place_of_birth": p.place_of_birth,
            "popularity": p.popularity
        } for p in people]
    }

@router.get("/people/{person_id}")
def get_person(person_id: int, db: Session = Depends(get_db)):
    repo = PeopleRepository(db)
    person = repo.get_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    credits = repo.get_media_credits(person_id)

    credit_rows = []

    for m in credits:
        role = "actor"
        character_name = None

        # media_people is represented by the association table.
        try:
            result = db.execute(
                text(
                    "SELECT role, character_name "
                    "FROM media_people "
                    "WHERE media_id = :media_id "
                    "AND person_id = :person_id "
                    "LIMIT 1"
                ),
                {
                    "media_id": m.id,
                    "person_id": person.id,
                },
            ).fetchone()

            if result:
                role = result[0] or "actor"
                character_name = result[1]
        except Exception:
            pass

        poster_url = None
        poster_path = getattr(m, "poster_path", None)

        # MediaItem may not store poster_path directly. Prefer the primary
        # poster from the artwork relationship, then fall back to any poster.
        for artwork in getattr(m, "artwork", []) or []:
            if getattr(artwork, "type", None) != "poster":
                continue

            url = getattr(artwork, "url", None) or getattr(artwork, "local_path", None)
            if url:
                poster_url = str(url)
                if getattr(artwork, "is_primary", False):
                    break

        if not poster_url and poster_path:
            poster_url = (
                poster_path
                if str(poster_path).startswith("http")
                else f"https://image.tmdb.org/t/p/w500{poster_path}"
            )

        credit_rows.append({
            "id": m.id,
            "title": m.title,
            "media_type": m.media_type.value if m.media_type else "movie",
            "role": role,
            "character_name": character_name,
            "poster_path": poster_path,
            "poster_url": poster_url,
        })

    return {
        "id": person.id,
        "name": person.name,
        "biography": person.biography,
        "profile_path": person.profile_path,
        "profile_url": (
            f"https://image.tmdb.org/t/p/w500{person.profile_path}"
            if person.profile_path and not str(person.profile_path).startswith("http")
            else person.profile_path
        ),
        "tmdb_id": person.tmdb_id,
        "imdb_id": person.imdb_id,
        "known_for_department": person.known_for_department,
        "birthday": person.birthday,
        "deathday": person.deathday,
        "place_of_birth": person.place_of_birth,
        "popularity": person.popularity,
        "credits": credit_rows,
    }
