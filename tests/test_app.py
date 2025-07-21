import os

# Provide defaults so importing the app doesn't fail
os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

from main import app
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
import pytest


def test_app_import():
    assert app.title == "Truck Stop MCP Helpdesk API"


def test_app_loads():
    assert app.title


@pytest.mark.asyncio
async def test_app_startup():
    async with LifespanManager(app):
        assert hasattr(app.state, "mcp")


@pytest.mark.asyncio
async def test_health_handles_db_failure(monkeypatch):
    async def fail_execute(self, *args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(AsyncSession, "execute", fail_execute)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["checks"]["database"]["status"] == "unhealthy"
