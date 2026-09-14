from fastapi import APIRouter, HTTPException
from pathlib import Path
from datetime import datetime
import shutil, sys, platform
from app.config import get_settings
from app.logging import get_logger

router = APIRouter()
logger = get_logger("api.system")

@router.get("/system/info")
def system_info():
    return {
        "application": "JMDB",
        "version": "1.0.0",
        "python": sys.version.split()[0],
        "platform": platform.platform()
    }

@router.post("/system/backup")
def create_backup():
    s = get_settings()
    db_path = Path(s.db_path)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="No database found")
    
    backup_dir = Path(s.data_dir) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"jmdb_backup_{ts}.db"
    shutil.copy2(db_path, backup_path)
    
    return {"status": "success", "backup_path": str(backup_path)}

@router.get("/system/backups")
def list_backups():
    s = get_settings()
    backup_dir = Path(s.data_dir) / "backups"
    if not backup_dir.exists():
        return {"backups": []}
    
    backups = []
    for f in sorted(backup_dir.glob("jmdb_backup_*.db"), reverse=True):
        backups.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        })
    
    return {"backups": backups}

@router.post("/system/restore")
def restore_backup(data: dict):
    s = get_settings()
    backup_path = Path(data.get("backup_path", ""))
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    
    shutil.copy2(backup_path, Path(s.db_path))
    return {"status": "restored"}

@router.get("/system/diagnostics")
def diagnostics():
    s = get_settings()
    db = Path(s.db_path)
    return {
        "db_path": s.db_path,
        "db_exists": db.exists(),
        "db_size": db.stat().st_size if db.exists() else 0,
        "data_dir": s.data_dir
    }

@router.post("/system/reset-settings")
def reset_settings():
    from app.database.connection import get_session_local
    from app.database.models import ApplicationSetting
    s = get_settings()
    db = get_session_local(s.db_path)()
    try:
        db.query(ApplicationSetting).delete()
        db.commit()
        return {"status": "reset"}
    finally:
        db.close()
