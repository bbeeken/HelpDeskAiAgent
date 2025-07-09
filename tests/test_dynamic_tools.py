import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_dynamic_tool_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/echo", json={"text": "hi"})
        assert resp.status_code == 200
        assert resp.json() == {"echo": "hi"}

        resp = await client.post("/echo", json={"text": "hi", "extra": 1})
        assert resp.status_code == 422

        resp = await client.post("/add", json={"a": 2, "b": 3})
        assert resp.status_code == 200
        assert resp.json() == {"result": 5}


@pytest.mark.asyncio
async def test_tools_list_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert any(t["name"] == "echo" for t in tools)
