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
async def test_ai_suggest_response_stream(client, monkeypatch):
    async def dummy_stream(ticket, context=""):
        yield "part1"
        yield "part2"

    monkeypatch.setattr("tools.ai_tools.ai_stream_response", dummy_stream)
    monkeypatch.setattr("api.routes.ai_stream_response", dummy_stream)

    ticket = {
        "Ticket_ID": 1,
        "Subject": "Subj",
        "Ticket_Body": "Body",
        "Ticket_Status_ID": 1,
        "Ticket_Contact_Name": "Name",
        "Ticket_Contact_Email": "a@example.com",
    }

    async with client.stream("POST", "/ai/suggest_response/stream", json=ticket) as resp:
        assert resp.status_code == 200
        chunks = [chunk async for chunk in resp.aiter_text()]

    # verify SSE framing and plain text reconstruction
    all_text = "".join(chunks)
    lines = [line for line in all_text.splitlines() if line.startswith("data:")]
    assert lines
    assert all(line.startswith("data:") for line in lines)
    text = "".join(line.removeprefix("data:").strip() for line in lines)
    assert text == "part1part2"
