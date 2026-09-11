from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.system import router as system_router
from app.database.migrations import migrate


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate()
    yield


app = FastAPI(
    title="JMDB",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(system_router)


@app.get("/")
def root():
    return {
        "name": "JMDB",
        "version": "0.1.0",
        "status": "running",
    }
