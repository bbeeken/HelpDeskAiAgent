import pytest
from httpx import AsyncClient, ASGITransport
from main import app
import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_ai_suggest_response(client, monkeypatch):
    async def fake(ticket, context=""):
        return "hello"

    monkeypatch.setattr("tools.ai_tools.ai_suggest_response", fake)
    monkeypatch.setattr("api.routes.ai_suggest_response", fake)

    resp = await client.post("/ai/suggest_response", json={"Ticket_ID": 1})
    assert resp.status_code == 200
    assert resp.json() == {"response": "hello"}
