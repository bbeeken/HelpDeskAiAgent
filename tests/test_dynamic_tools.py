import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_dynamic_tool_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/g_ticket", json={"ticket_id": 1})
        assert resp.status_code == 200
        assert resp.json() in ({"ticket_id": 1}, None)

        resp = await client.post("/g_ticket", json={"ticket_id": 1, "extra": 1})
        assert resp.status_code == 422

        resp = await client.post("/g_ticket", json={})
        assert resp.status_code == 422

        resp = await client.post("/g_ticket", json={"ticket_id": "one"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_dynamic_tool_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/g_ticket", json={"ticket_id": "bad"})
        assert resp.status_code == 422

        resp = await client.post("/g_ticket", json={})
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
        assert "g_ticket" in names
        assert "l_tkts" in names
