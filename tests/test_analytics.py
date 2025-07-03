import os
from datetime import datetime, timedelta, UTC

import pytest
from httpx import AsyncClient
from main import app
from db.models import Ticket
from db.mssql import SessionLocal
from tools.ticket_tools import create_ticket

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")


import pytest_asyncio


def fake_create(*args, **kwargs):
    """Return a dummy OpenAI chat completion response."""
    class Msg:
        content = "ok"

    class Choice:
        message = Msg()

    return type("Resp", (), {"choices": [Choice()]})()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

async def _add_ticket(**kwargs):
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="subj",
            Ticket_Body="body",
            Ticket_Contact_Name="name",
            Ticket_Contact_Email=kwargs.get("Ticket_Contact_Email", "c@example.com"),
            Ticket_Status_ID=kwargs.get("Ticket_Status_ID", 1),
            Site_ID=kwargs.get("Site_ID"),
            Assigned_Email=kwargs.get("Assigned_Email"),
            Created_Date=kwargs.get("Created_Date", datetime.now(UTC)),
        )

        await create_ticket(db, ticket)

        return ticket

@pytest.mark.asyncio
async def test_analytics_status(client: AsyncClient):
    await _add_ticket(Ticket_Status_ID=1)
    await _add_ticket(Ticket_Status_ID=1)
    await _add_ticket(Ticket_Status_ID=2)

    resp = await client.get("/analytics/status")
    assert resp.status_code == 200
    data = {item[0]: item[1] for item in resp.json()}
    assert data == {1: 2, 2: 1}

@pytest.mark.asyncio
async def test_analytics_open_by_site(client: AsyncClient):
    await _add_ticket(Site_ID=1, Ticket_Status_ID=1)
    await _add_ticket(Site_ID=1, Ticket_Status_ID=2)
    await _add_ticket(Site_ID=2, Ticket_Status_ID=1)
    await _add_ticket(Site_ID=2, Ticket_Status_ID=3)  # closed

    resp = await client.get("/analytics/open_by_site")
    assert resp.status_code == 200
    data = {item[0]: item[1] for item in resp.json()}
    assert data == {1: 2, 2: 1}

@pytest.mark.asyncio
async def test_analytics_sla_breaches(client: AsyncClient):
    old = datetime.now(UTC) - timedelta(days=3)
    await _add_ticket(Created_Date=old)
    await _add_ticket()
    resp = await client.get("/analytics/sla_breaches", params={"sla_days": 2})
    assert resp.status_code == 200
    assert resp.json() == {"breaches": 1}

@pytest.mark.asyncio
async def test_analytics_open_by_user(client: AsyncClient):
    await _add_ticket(Assigned_Email="tech@example.com", Ticket_Status_ID=1)
    await _add_ticket(Assigned_Email="tech@example.com", Ticket_Status_ID=1)
    await _add_ticket(Assigned_Email="other@example.com", Ticket_Status_ID=1)
    await _add_ticket(Assigned_Email="tech@example.com", Ticket_Status_ID=3)

    resp = await client.get("/analytics/open_by_user")
    assert resp.status_code == 200
    data = {item[0]: item[1] for item in resp.json()}
    assert data == {"tech@example.com": 2, "other@example.com": 1}

@pytest.mark.asyncio
async def test_analytics_waiting_on_user(client: AsyncClient):
    await _add_ticket(Ticket_Status_ID=4, Ticket_Contact_Email="user1@example.com")
    await _add_ticket(Ticket_Status_ID=4, Ticket_Contact_Email="user1@example.com")
    await _add_ticket(Ticket_Status_ID=4, Ticket_Contact_Email="user2@example.com")
    await _add_ticket(Ticket_Status_ID=1, Ticket_Contact_Email="user1@example.com")

    resp = await client.get("/analytics/waiting_on_user")
    assert resp.status_code == 200
    data = {item[0]: item[1] for item in resp.json()}
    assert data == {"user1@example.com": 2, "user2@example.com": 1}

@pytest.mark.asyncio
async def test_ai_suggest_response(client: AsyncClient, monkeypatch):
    from ai import openai_agent

    class DummyClient:
        class Chat:
            class Completions:
                @staticmethod
                def create(*_, **__):
                    class Msg:
                        content = "ok"

                    class Choice:
                        message = Msg()

                    return type("Resp", (), {"choices": [Choice()]})()

    from ai import openai_agent
    openai_agent._get_client()
    assert openai_agent.openai_client is not None
    monkeypatch.setattr(openai_agent.openai_client.chat.completions, "create", fake_create)


    payload = {
        "Subject": "AI", "Ticket_Body": "body",
        "Ticket_Contact_Name": "Tester", "Ticket_Contact_Email": "t@example.com"
    }
    ticket = (await client.post("/ticket", json=payload)).json()
    resp = await client.post("/ai/suggest_response", params={"context": "test"}, json=ticket)
    assert resp.status_code == 200
    assert resp.json()["response"] == "ok"
