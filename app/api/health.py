from fastapi import APIRouter

from app.config import DATABASE_PATH
from app.database.connection import get_connection

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    with get_connection() as db:
        db.execute("SELECT 1").fetchone()

    return {
        "ok": True,
        "service": "jmdb-backend",
        "database": str(DATABASE_PATH),
    }
