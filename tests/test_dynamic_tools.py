import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_dynamic_tool_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_ticket", json={"ticket_id": 1})
        assert resp.status_code == 200
        assert resp.json() == {"ticket_id": 1}

        resp = await client.post("/get_ticket", json={"ticket_id": 1, "extra": 1})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tools_list_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert any(t["name"] == "get_ticket" for t in tools)
