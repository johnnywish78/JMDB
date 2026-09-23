from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.logging import setup_logging, get_logger
from app.database.connection import init_database, get_engine
from app.database.migrations import run_migrations
from app.api import health, media, library, search, people, services, settings, playback, system, browser

logger = get_logger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level, str(Path(s.data_dir) / "logs"))
    logger.info(f"JMDB Backend v{s.app_version} starting on {s.backend_host}:{s.backend_port}")
    init_database(s)
    run_migrations(get_engine(s.db_path))
    logger.info("Backend ready")
    yield
    logger.info("Backend shutting down")

app = FastAPI(title="JMDB", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve the Electron UI from the same local HTTP origin as the JMDB backend.
# This avoids the file:// origin used by loadFile(), which is problematic
# for embedded web content that requires a real HTTP origin/referrer.
ELECTRON_SRC = Path(__file__).resolve().parents[1] / "electron" / "src"

if not ELECTRON_SRC.is_dir():
    raise RuntimeError(f"JMDB Electron UI directory not found: {ELECTRON_SRC}")

from fastapi.staticfiles import StaticFiles

# Include all routers
app.include_router(health.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(people.router, prefix="/api")
app.include_router(services.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(playback.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(browser.router)

# Electron UI. /api/* remains handled exclusively by the API routers above.
app.mount("/ui", StaticFiles(directory=str(ELECTRON_SRC), html=True), name="electron-ui")

@app.get("/")
def root():
    return {"name": "JMDB", "version": "1.0.0", "status": "running"}
