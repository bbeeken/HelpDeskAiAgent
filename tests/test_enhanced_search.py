import pytest
from datetime import datetime, UTC, timedelta
from httpx import AsyncClient, ASGITransport

from main import app
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager


@pytest.mark.asyncio
async def test_enhanced_search_direct_parameters():
    async with SessionLocal() as db:
        t1 = Ticket(
            Subject="Printer Error",
            Ticket_Body="HP printer shows error code 42",
            Ticket_Contact_Name="User1",
            Ticket_Contact_Email="user1@example.com",
            Ticket_Status_ID=1,
            Severity_ID=2,
            Site_ID=1,
            Created_Date=datetime.now(UTC),
        )
        t2 = Ticket(
            Subject="Network Issue",
            Ticket_Body="Cannot connect to email server",
            Ticket_Contact_Name="User2",
            Ticket_Contact_Email="user2@example.com",
            Ticket_Status_ID=2,
            Severity_ID=1,
            Site_ID=2,
            Assigned_Email="tech@example.com",
            Created_Date=datetime.now(UTC) - timedelta(days=1),
        )
        await TicketManager().create_ticket(db, t1)
        await TicketManager().create_ticket(db, t2)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/search_tickets", json={"status": "open", "limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        ticket_ids = [t["Ticket_ID"] for t in data["data"]]
        assert t1.Ticket_ID in ticket_ids
        assert t2.Ticket_ID in ticket_ids

        resp = await client.post("/search_tickets", json={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        ticket_ids = [t["Ticket_ID"] for t in data["data"]]
        assert t2.Ticket_ID in ticket_ids
        assert t1.Ticket_ID not in ticket_ids

        resp = await client.post("/search_tickets", json={"site_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        ticket_ids = [t["Ticket_ID"] for t in data["data"]]
        assert t1.Ticket_ID in ticket_ids
        assert t2.Ticket_ID not in ticket_ids

        resp = await client.post("/search_tickets", json={"unassigned_only": True})
        assert resp.status_code == 200
        data = resp.json()
        ticket_ids = [t["Ticket_ID"] for t in data["data"]]
        assert t1.Ticket_ID in ticket_ids
        assert t2.Ticket_ID not in ticket_ids


@pytest.mark.asyncio
async def test_enhanced_search_ai_features():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Email Server Down",
            Ticket_Body="The main email server is not responding to requests",
            Ticket_Contact_Name="Admin",
            Ticket_Contact_Email="admin@example.com",
            Ticket_Status_ID=1,
            Created_Date=datetime.now(UTC),
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/search_tickets",
            json={
                "text": "email server",
                "include_relevance_score": True,
                "include_highlights": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        ticket = data["data"][0]
        assert "relevance_score" in ticket
        assert 0 < ticket["relevance_score"] <= 1
        assert "highlights" in ticket
        assert "<em>" in ticket["highlights"]["subject"]
        assert "metadata" in ticket
        assert "age_days" in ticket["metadata"]
        assert "is_overdue" in ticket["metadata"]
        assert "complexity_estimate" in ticket["metadata"]


@pytest.mark.asyncio
async def test_backward_compatibility_aliases():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Test Ticket",
            Ticket_Body="Test body content",
            Ticket_Contact_Name="TestUser",
            Ticket_Contact_Email="test@example.com",
            Ticket_Status_ID=1,
            Created_Date=datetime.now(UTC),
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/search_tickets", json={"query": "test"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) > 0

        resp = await client.post("/search_tickets", json={"user_identifier": "test@example.com"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) > 0


@pytest.mark.asyncio
async def test_search_tickets_accepts_null_status():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Null Status Ticket",
            Ticket_Body="Test body content",
            Ticket_Contact_Name="TestUser",
            Ticket_Contact_Email="test@example.com",
            Ticket_Status_ID=1,
            Created_Date=datetime.now(UTC),
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/search_tickets", json={"status": None})
        assert resp.status_code == 200
        data = resp.json()
        ticket_ids = [item["Ticket_ID"] for item in data["data"]]
        assert t.Ticket_ID in ticket_ids


@pytest.mark.asyncio
async def test_enhanced_search_date_filtering():
    async with SessionLocal() as db:
        old_ticket = Ticket(
            Subject="Old Issue",
            Ticket_Body="Old problem",
            Ticket_Contact_Name="User",
            Ticket_Contact_Email="user@example.com",
            Ticket_Status_ID=1,
            Created_Date=datetime(2024, 1, 1, tzinfo=UTC),
        )
        new_ticket = Ticket(
            Subject="New Issue",
            Ticket_Body="Recent problem",
            Ticket_Contact_Name="User",
            Ticket_Contact_Email="user@example.com",
            Ticket_Status_ID=1,
            Created_Date=datetime.now(UTC),
        )
        await TicketManager().create_ticket(db, old_ticket)
        await TicketManager().create_ticket(db, new_ticket)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/search_tickets", json={"created_after": "2024-06-01T00:00:00Z"})
        assert resp.status_code == 200
        data = resp.json()
        ids = [t["Ticket_ID"] for t in data["data"]]
        assert new_ticket.Ticket_ID in ids
        assert old_ticket.Ticket_ID not in ids

        resp = await client.post("/search_tickets", json={"created_before": "2024-06-01T00:00:00Z"})
        assert resp.status_code == 200
        data = resp.json()
        ids = [t["Ticket_ID"] for t in data["data"]]
        assert old_ticket.Ticket_ID in ids
        assert new_ticket.Ticket_ID not in ids


@pytest.mark.asyncio
async def test_enhanced_search_invalid_dates():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/search_tickets", json={"created_after": "bad"})
        assert resp.status_code == 422
        resp = await client.post("/search_tickets", json={"created_before": "bad"})
        assert resp.status_code == 422
