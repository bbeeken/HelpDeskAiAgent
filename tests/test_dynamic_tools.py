import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_dynamic_tool_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_ticket", json={"ticket_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in {"success", "error"}

        resp = await client.post("/get_ticket", json={"ticket_id": 1, "extra": 1})
        assert resp.status_code == 422

        resp = await client.post("/get_ticket", json={})
        assert resp.status_code == 422

        resp = await client.post("/get_ticket", json={"ticket_id": "one"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_dynamic_tool_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_ticket", json={"ticket_id": "bad"})
        assert resp.status_code == 422

        resp = await client.post("/get_ticket", json={})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tools_list_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools")
        assert resp.status_code == 200
        data = resp.json()
        tools = data["tools"] if isinstance(data, dict) else data
        names = {t["name"] for t in tools}
        assert "get_ticket" in names
        assert "list_tickets" in names
