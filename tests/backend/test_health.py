from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "JMDB"
    assert data["status"] == "running"


def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200

    data = response.json()

    assert data["ok"] is True
    assert data["service"] == "jmdb-backend"


def test_system_status():
    response = client.get("/api/system/status")

    assert response.status_code == 200

    data = response.json()

    from app.database.migrations import SCHEMA_VERSION

    assert data["database_schema"] == SCHEMA_VERSION
    assert data["media_count"] == 0
