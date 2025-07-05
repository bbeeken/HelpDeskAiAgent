import json
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from httpx_sse import EventSource
from main import app

@pytest.mark.asyncio
async def test_mcp_roundtrip():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/mcp") as resp:
            assert resp.status_code == 200
            source = EventSource(resp)
            events = source.aiter_sse()
            first = await asyncio.wait_for(anext(events), timeout=1)
            assert first.event == "endpoint"
            post_url = first.data
            assert post_url.startswith("/mcp/")

            payload = {"jsonrpc": "2.0", "id": 1, "result": "pong"}
            post_resp = await client.post(post_url, json=payload)
            assert post_resp.status_code == 202

            second = await asyncio.wait_for(anext(events), timeout=1)
            assert second.event == "message"
            assert json.loads(second.data) == payload
            await source.aclose()
