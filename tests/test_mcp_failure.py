import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from fastapi_mcp import FastApiMCP

from main import app


@pytest.mark.asyncio
async def test_mcp_initialization_failure(monkeypatch):
    def boom(self, *args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(FastApiMCP, "mount", boom)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with LifespanManager(app):
        assert not getattr(app.state, "mcp_ready", False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/tools")
            assert resp.status_code == 503

            # Subpaths like /mcp/messages/123 should also be blocked
            resp = await ac.post("/mcp/messages/123", json={})
            assert resp.status_code == 503
