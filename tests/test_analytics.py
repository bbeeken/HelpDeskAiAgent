import os
from datetime import datetime, timedelta, UTC

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from db.models import Ticket
from db.mssql import SessionLocal
from tools.ticket_tools import create_ticket

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")


import pytest_asyncio


async def fake_create(*args, **kwargs):
    """Return a dummy OpenAI chat completion response."""
    class Msg:
        content = "ok"

    class Choice:
        message = Msg()

    return type("Resp", (), {"choices": [Choice()]})()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
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
    data = {item["status_id"]: item["count"] for item in resp.json()}
    assert data == {1: 2, 2: 1}
    assert all("status_label" in item for item in resp.json())

@pytest.mark.asyncio
async def test_analytics_open_by_site(client: AsyncClient):
    await _add_ticket(Site_ID=1, Ticket_Status_ID=1)
    await _add_ticket(Site_ID=1, Ticket_Status_ID=2)
    await _add_ticket(Site_ID=2, Ticket_Status_ID=1)
    await _add_ticket(Site_ID=2, Ticket_Status_ID=3)  # closed

    resp = await client.get("/analytics/open_by_site")
    assert resp.status_code == 200
    data = {item["site_id"]: item["count"] for item in resp.json()}
    assert data == {1: 2, 2: 1}
    assert all("site_label" in item for item in resp.json())

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
    data = {item["assigned_email"]: item["count"] for item in resp.json()}
    assert data == {"tech@example.com": 2, "other@example.com": 1}

@pytest.mark.asyncio
async def test_analytics_waiting_on_user(client: AsyncClient):
    await _add_ticket(Ticket_Status_ID=4, Ticket_Contact_Email="user1@example.com")
    await _add_ticket(Ticket_Status_ID=4, Ticket_Contact_Email="user1@example.com")
    await _add_ticket(Ticket_Status_ID=4, Ticket_Contact_Email="user2@example.com")
    await _add_ticket(Ticket_Status_ID=1, Ticket_Contact_Email="user1@example.com")

    resp = await client.get("/analytics/waiting_on_user")
    assert resp.status_code == 200
    data = {item["contact_email"]: item["count"] for item in resp.json()}
    assert data == {"user1@example.com": 2, "user2@example.com": 1}


@pytest.mark.asyncio
async def test_sla_breaches_with_filters(client: AsyncClient):
    old = datetime.now(UTC) - timedelta(days=5)
    await _add_ticket(
        Created_Date=old,
        Assigned_Email="tech@example.com",
        Ticket_Status_ID=1,
    )
    await _add_ticket(
        Created_Date=old,
        Assigned_Email="other@example.com",
        Ticket_Status_ID=1,
    )
    await _add_ticket(Created_Date=old, Ticket_Status_ID=3)

    resp = await client.get(
        "/analytics/sla_breaches",
        params={"Assigned_Email": "tech@example.com", "sla_days": 2},
    )
    assert resp.status_code == 200
    assert resp.json() == {"breaches": 1}

    resp = await client.get(
        "/analytics/sla_breaches",
        params={"status_id": [3], "sla_days": 2},
    )
    assert resp.status_code == 200
    assert resp.json() == {"breaches": 1}


@pytest.mark.asyncio

async def test_sla_breaches_excludes_non_open(client: AsyncClient):
    """Closed or waiting tickets should not count towards SLA breaches."""
    old = datetime.now(UTC) - timedelta(days=5)
    await _add_ticket(Created_Date=old, Ticket_Status_ID=1)
    await _add_ticket(Created_Date=old, Ticket_Status_ID=4)
    await _add_ticket(Created_Date=old, Ticket_Status_ID=3)

    resp = await client.get("/analytics/sla_breaches", params={"sla_days": 2})
    assert resp.status_code == 200
    # Only the open ticket should be counted
    assert resp.json() == {"breaches": 1}

    resp = await client.get(
        "/analytics/sla_breaches",
        params={"status_id": [3], "sla_days": 2},

    )
    assert resp.status_code == 200
    assert resp.json() == {"breaches": 1}


@pytest.mark.asyncio
async def test_ticket_trend(client: AsyncClient):
    now = datetime.now(UTC)
    await _add_ticket(Created_Date=now - timedelta(days=2))
    await _add_ticket(Created_Date=now - timedelta(days=1))
    await _add_ticket(Created_Date=now - timedelta(days=1))

    resp = await client.get("/analytics/trend", params={"days": 3})
    assert resp.status_code == 200
    data = {item["date"]: item["count"] for item in resp.json()}
    assert data[(now - timedelta(days=2)).date().isoformat()] == 1
    assert data[(now - timedelta(days=1)).date().isoformat()] == 2
