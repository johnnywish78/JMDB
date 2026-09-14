from fastapi import APIRouter
from datetime import datetime
import sys

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "python": sys.version.split()[0]
    }
