from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None

def get_engine(db_path: str):
    global _engine
    if _engine is not None:
        return _engine
    
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    @event.listens_for(_engine, "connect")
    def set_pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.close()
    
    return _engine

def get_session_local(db_path: str):
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(db_path)
        )
    return _SessionLocal

def init_database(settings):
    get_engine(settings.db_path)
    get_session_local(settings.db_path)
