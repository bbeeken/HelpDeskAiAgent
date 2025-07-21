import pytest
from httpx import AsyncClient, ASGITransport
from main import app

import pytest_asyncio


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_unhandled_exception_returns_json(client, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("boom")

    from api import routes
    monkeypatch.setattr(routes.TicketManager, "get_ticket", boom)

    resp = await client.get("/ticket/1")
    assert resp.status_code == 500
    data = resp.json()
    assert data["detail"] == "boom"
