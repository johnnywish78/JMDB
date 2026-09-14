from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.models import Person

class PeopleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, person_id: int) -> Optional[Person]:
        return self.db.query(Person).filter(Person.id == person_id).first()

    def search(self, query: str, limit: int = 50) -> List[Person]:
        return self.db.query(Person).filter(Person.name.ilike(f"%{query}%")).limit(limit).all()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Person]:
        return self.db.query(Person).order_by(Person.name).offset(offset).limit(limit).all()

    def get_media_credits(self, person_id: int) -> List:
        person = self.get_by_id(person_id)
        return person.media_items if person else []
