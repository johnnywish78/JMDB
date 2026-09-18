from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from datetime import datetime
from typing import List, Optional
from app.database.models import MediaItem, MediaFile, WatchProgress, MediaType, MediaStatus

class MediaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, item: MediaItem) -> MediaItem:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, item_id: int) -> Optional[MediaItem]:
        return self.db.query(MediaItem).filter(MediaItem.id == item_id).first()

    def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
        media_type: Optional[str] = None,
        search: Optional[str] = None,
        favorite: Optional[bool] = None,
        sort: str = "newest",
    ) -> List[MediaItem]:
        q = self.db.query(MediaItem)

        if media_type:
            q = q.filter(MediaItem.media_type == MediaType(media_type))

        if favorite is not None:
            q = q.filter(MediaItem.favorite == favorite)

        if search:
            pattern = f"%{search}%"
            q = q.filter(
                or_(
                    MediaItem.title.ilike(pattern),
                    MediaItem.original_title.ilike(pattern),
                    MediaItem.description.ilike(pattern)
                )
            )

        sort_map = {
            "newest": (
                desc(MediaItem.created_at),
                desc(MediaItem.id),
            ),
            "oldest": (
                asc(MediaItem.created_at),
                asc(MediaItem.id),
            ),
            "title": (
                func.lower(MediaItem.title).asc(),
                asc(MediaItem.id),
            ),
            "rating": (
                desc(func.coalesce(MediaItem.rating, -1)),
                desc(MediaItem.id),
            ),
        }

        order_by = sort_map.get(sort, sort_map["newest"])

        return (
            q.order_by(*order_by)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_recently_added(self, limit: int = 20) -> List[MediaItem]:
        return self.db.query(MediaItem).order_by(desc(MediaItem.created_at)).limit(limit).all()

    def get_favorites(self, limit: int = 50) -> List[MediaItem]:
        return self.db.query(MediaItem).filter(MediaItem.favorite == True).limit(limit).all()

    def get_continue_watching(self, limit: int = 20) -> List[MediaItem]:
        return (self.db.query(MediaItem)
                .join(WatchProgress)
                .filter(
                    WatchProgress.completed == False,
                    WatchProgress.position > 0
                )
                .order_by(desc(WatchProgress.last_watched))
                .limit(limit)
                .all())

    def search(self, query: str, limit: int = 50) -> List[MediaItem]:
        pattern = f"%{query}%"
        return (self.db.query(MediaItem)
                .filter(or_(
                    MediaItem.title.ilike(pattern),
                    MediaItem.original_title.ilike(pattern),
                    MediaItem.description.ilike(pattern)
                ))
                .limit(limit)
                .all())

    def update(self, item: MediaItem) -> MediaItem:
        item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item_id: int):
        item = self.get_by_id(item_id)
        if item:
            self.db.delete(item)
            self.db.commit()

    def count(
        self,
        media_type: Optional[str] = None,
        favorite: Optional[bool] = None,
    ) -> int:
        q = self.db.query(func.count(MediaItem.id))

        if media_type:
            q = q.filter(MediaItem.media_type == MediaType(media_type))

        if favorite is not None:
            q = q.filter(MediaItem.favorite == favorite)

        return q.scalar() or 0

    def update_progress(self, media_item_id: int, position: float, 
                       duration: float, completed: bool = False):
        p = self.db.query(WatchProgress).filter(
            WatchProgress.media_item_id == media_item_id
        ).first()
        
        if not p:
            p = WatchProgress(
                media_item_id=media_item_id,
                position=position,
                duration=duration,
                completed=completed
            )
            self.db.add(p)
        else:
            p.position = position
            p.duration = duration
            p.completed = completed
            p.last_watched = datetime.utcnow()
        
        self.db.commit()

    def set_favorite(self, item_id: int, favorite: bool):
        item = self.get_by_id(item_id)
        if item:
            item.favorite = favorite
            self.db.commit()

    def add_file(self, media_item_id: int, file_path: str, file_name: str,
                 file_size: int = 0, file_format: str = "", duration: float = 0):
        mf = MediaFile(
            media_item_id=media_item_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            file_format=file_format,
            duration=duration
        )
        self.db.add(mf)
        self.db.commit()
        self.db.refresh(mf)
        return mf
