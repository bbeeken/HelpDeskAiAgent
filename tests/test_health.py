from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"status", "timestamp", "version", "uptime", "checks"}
    assert data["status"] in {"healthy", "degraded", "unhealthy"}
    assert "database" in data["checks"]
