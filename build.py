#!/usr/bin/env python3
import os
from pathlib import Path

PROJECT = Path(__file__).parent

def write_file(rel_path: str, content: str):
    full_path = PROJECT / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    print(f"✓ {rel_path}")

print("Starting JMDB project creation...")

write_file("requirements.txt", """fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
httpx>=0.25.0
psutil>=5.9.0
""")

write_file("app/__init__.py", '"""JMDB Backend."""\n')

write_file("app/config.py", """from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "JMDB"
    backend_port: int = 8765
    data_dir: str = str(Path(__file__).parent.parent / "data")
    db_path: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        base = Path(self.data_dir)
        base.mkdir(parents=True, exist_ok=True)
        if not self.db_path:
            self.db_path = str(base / "database" / "jmdb.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

def get_settings() -> Settings:
    return Settings()
""")

write_file("app/database/__init__.py", '"""Database."""\n')

write_file("app/database/connection.py", """from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None

def get_engine(db_path):
    global _engine
    if _engine is not None:
        return _engine
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    @event.listens_for(_engine, "connect")
    def set_pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()
    return _engine

def get_session_local(db_path):
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(db_path))
    return _SessionLocal
""")

write_file("app/database/models.py", """from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class MediaType(str, enum.Enum):
    MOVIE = "movie"
    MUSIC = "music"

class MediaItem(Base):
    __tablename__ = "media_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    media_type = Column(Enum(MediaType), default=MediaType.MOVIE)
    title = Column(String(500), nullable=False)
    year = Column(Integer)
    rating = Column(Float)
    favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
""")

write_file("app/api/__init__.py", '"""API."""\n')

write_file("app/api/health.py", """from fastapi import APIRouter
from datetime import datetime
import sys

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0", "python": sys.version.split()[0]}
""")

write_file("app/main.py", """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database.connection import get_engine
from app.database.models import Base
from app.api import health

settings = get_settings()
engine = get_engine(settings.db_path)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="JMDB", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router, prefix="/api")

@app.get("/")
def root():
    return {"name": "JMDB", "status": "running"}
""")

write_file("run.py", """#!/usr/bin/env python3
import subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

def validate_deps():
    try:
        import fastapi, uvicorn, sqlalchemy, pydantic
        print("[JMDB] Dependencies OK")
    except ImportError:
        print("ERROR: Run 'pip install -r requirements.txt' first")
        sys.exit(1)

def start_backend():
    port = 8765
    print(f"[JMDB] Starting backend on 127.0.0.1:{port}")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT)
    )

def wait_backend(port, timeout=15):
    url = f"http://127.0.0.1:{port}/api/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            if urllib.request.urlopen(url, timeout=2).getcode() == 200:
                print("[JMDB] ✅ Backend is healthy and running!")
                print("[JMDB] Open http://127.0.0.1:8765 in your browser.")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

if __name__ == "__main__":
    print("="*50)
    print("  JMDB - Johnny's Media Database v1.0.0")
    print("="*50)
    validate_deps()
    bp = start_backend()
    if wait_backend(8765):
        try:
            bp.wait()
        except KeyboardInterrupt:
            print("\\n[JMDB] Shutting down...")
            bp.terminate()
""")

print("\n✅ Project structure created successfully!")
print("Next: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt")
