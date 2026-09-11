from fastapi import APIRouter

from app.database.connection import get_connection

router = APIRouter(prefix="/api/system")


@router.get("/status")
def status():
    with get_connection() as db:
        version = db.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ).fetchone()

        media_count = db.execute(
            "SELECT COUNT(*) AS count FROM media_items"
        ).fetchone()["count"]

    return {
        "database_schema": version["version"] if version else 0,
        "media_count": media_count,
    }
