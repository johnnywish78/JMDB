from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, 
    ForeignKey, Enum, Table, Index
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class MediaType(str, enum.Enum):
    MOVIE = "movie"
    TV_SHOW = "tv_show"
    EPISODE = "episode"
    MUSIC = "music"
    OTHER = "other"

class MediaStatus(str, enum.Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"

# Association tables
media_genres = Table("media_genres", Base.metadata,
    Column("media_id", Integer, ForeignKey("media_items.id"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id"), primary_key=True),
)

media_people = Table("media_people", Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("media_id", Integer, ForeignKey("media_items.id"), primary_key=True),
    Column("person_id", Integer, ForeignKey("people.id"), primary_key=True),
    Column("role", String(50), default="actor"),
    Column("character_name", String(255)),
)

collection_items = Table("collection_items", Base.metadata,
    Column("collection_id", Integer, ForeignKey("collections.id"), primary_key=True),
    Column("media_id", Integer, ForeignKey("media_items.id"), primary_key=True),
)

class Library(Base):
    __tablename__ = "libraries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    media_type = Column(Enum(MediaType), default=MediaType.MOVIE)
    path = Column(String(1024), nullable=False)
    scan_status = Column(String(50), default="idle")
    last_scan_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    media_items = relationship("MediaItem", back_populates="library", cascade="all, delete-orphan")

class MediaItem(Base):
    __tablename__ = "media_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    library_id = Column(Integer, ForeignKey("libraries.id"))
    
    media_type = Column(Enum(MediaType), default=MediaType.MOVIE)
    title = Column(String(500), nullable=False)
    original_title = Column(String(500))
    description = Column(Text)
    
    year = Column(Integer)
    release_date = Column(String(50))
    runtime = Column(Integer)

    # TV episode metadata
    season_number = Column(Integer)
    episode_number = Column(Integer)
    episode_title = Column(String(500))
    
    rating = Column(Float)
    votes = Column(Integer, default=0)
    
    favorite = Column(Boolean, default=False)
    status = Column(Enum(MediaStatus), default=MediaStatus.AVAILABLE)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scanned_at = Column(DateTime)
    
    library = relationship("Library", back_populates="media_items")
    files = relationship("MediaFile", back_populates="media_item", cascade="all, delete-orphan")
    genres = relationship("Genre", secondary=media_genres, back_populates="media_items")
    people = relationship("Person", secondary=media_people, back_populates="media_items")
    artwork = relationship("Artwork", back_populates="media_item", cascade="all, delete-orphan")
    external_ids = relationship("ExternalID", back_populates="media_item", cascade="all, delete-orphan")
    watch_progress = relationship("WatchProgress", back_populates="media_item", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_media_title", "title"),
        Index("idx_media_type", "media_type"),
        Index("idx_media_year", "year"),
    )

class MediaFile(Base):
    __tablename__ = "media_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    media_item_id = Column(Integer, ForeignKey("media_items.id"), nullable=False)
    
    file_path = Column(String(2048), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    file_format = Column(String(20))
    
    duration = Column(Float)
    video_codec = Column(String(50))
    audio_codec = Column(String(50))
    resolution = Column(String(20))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime)
    
    media_item = relationship("MediaItem", back_populates="files")

class Genre(Base):
    __tablename__ = "genres"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    
    media_items = relationship("MediaItem", secondary=media_genres, back_populates="genres")

class Person(Base):
    __tablename__ = "people"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    biography = Column(Text)
    profile_path = Column(String(500))
    
    media_items = relationship("MediaItem", secondary=media_people, back_populates="people")

class Collection(Base):
    __tablename__ = "collections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_favorite = Column(Boolean, default=False)
    is_custom = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    items = relationship("MediaItem", secondary=collection_items)

class WatchProgress(Base):
    __tablename__ = "watch_progress"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    media_item_id = Column(Integer, ForeignKey("media_items.id"), nullable=False, unique=True)
    
    position = Column(Float, default=0.0)
    duration = Column(Float, default=0.0)
    completed = Column(Boolean, default=False)
    last_watched = Column(DateTime, default=datetime.utcnow)
    
    media_item = relationship("MediaItem", back_populates="watch_progress")

class Artwork(Base):
    __tablename__ = "artwork"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    media_item_id = Column(Integer, ForeignKey("media_items.id"), nullable=False)
    
    type = Column(String(50), nullable=False)
    url = Column(String(1024))
    local_path = Column(String(1024))
    is_primary = Column(Boolean, default=False)
    width = Column(Integer)
    height = Column(Integer)
    
    media_item = relationship("MediaItem", back_populates="artwork")

class ExternalID(Base):
    __tablename__ = "external_ids"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    media_item_id = Column(Integer, ForeignKey("media_items.id"), nullable=False)
    
    provider = Column(String(50), nullable=False)
    external_id = Column(String(100), nullable=False)
    url = Column(String(500))
    
    media_item = relationship("MediaItem", back_populates="external_ids")

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50), default="metadata")
    enabled = Column(Boolean, default=False)
    configured = Column(Boolean, default=False)
    api_key = Column(String(255))
    
    health_status = Column(String(50), default="unknown")
    last_connected = Column(DateTime)
    last_error = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ApplicationSetting(Base):
    __tablename__ = "application_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text)
    category = Column(String(50), default="general")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BrowserHistory(Base):
    __tablename__ = "browser_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(500))
    visited_at = Column(DateTime, default=datetime.utcnow, index=True)

class BrowserBookmark(Base):
    __tablename__ = "browser_bookmarks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(500))
    favicon = Column(String(500))
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class BrowserSetting(Base):
    __tablename__ = "browser_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text)
    category = Column(String(50), default="general")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
