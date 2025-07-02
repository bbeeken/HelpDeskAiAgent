import pytest
import pytest_asyncio
import httpx
from main import app


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_ok(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["db"] == "ok"
    assert "uptime" in data
    assert "version" in data
