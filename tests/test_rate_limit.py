import openai
import pytest
import pytest_asyncio
import httpx
from main import app


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

def _patch_openai(monkeypatch):
    def fake_create(*args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}
    monkeypatch.setattr(openai.ChatCompletion, "create", fake_create)

async def _create_ticket(client: httpx.AsyncClient):
    payload = {
        "Subject": "Rate", "Ticket_Body": "body",
        "Ticket_Contact_Name": "Tester", "Ticket_Contact_Email": "t@example.com"
    }
    resp = await client.post("/ticket", json=payload)
    assert resp.status_code == 200
    return resp.json()

@pytest.mark.asyncio
async def test_ai_suggest_response_rate_limit(client: httpx.AsyncClient, monkeypatch):
    _patch_openai(monkeypatch)
    from limiter import limiter
    limiter.reset()
    ticket = await _create_ticket(client)
    # First 10 requests succeed
    for _ in range(10):
        r = await client.post("/ai/suggest_response", json=ticket)
        assert r.status_code == 200
    # 11th request is blocked
    r = await client.post("/ai/suggest_response", json=ticket)
    assert r.status_code == 429

