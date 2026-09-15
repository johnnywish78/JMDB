from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import List, Optional
from app.database.models import Library, MediaType

class LibraryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, path: str, media_type: str = "movie") -> Optional[Library]:
        existing = self.find_by_path(path)
        if existing:
            return None
        
        lib = Library(
            name=name,
            path=path,
            media_type=MediaType(media_type)
        )
        self.db.add(lib)
        self.db.commit()
        self.db.refresh(lib)
        return lib

    def find_by_path(self, path: str) -> Optional[Library]:
        return self.db.query(Library).filter(Library.path == path).first()

    def get_by_id(self, library_id: int) -> Optional[Library]:
        return self.db.query(Library).filter(Library.id == library_id).first()

    def get_all(self) -> List[Library]:
        return self.db.query(Library).order_by(Library.name).all()

    def delete(self, library_id: int):
        lib = self.get_by_id(library_id)
        if lib:
            self.db.delete(lib)
            self.db.commit()

    def update_scan_status(self, library_id: int, status: str):
        lib = self.get_by_id(library_id)
        if lib:
            lib.scan_status = status
            if status == "completed":
                lib.last_scan_at = datetime.utcnow()
            self.db.commit()
