import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC

from main import app
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager


@pytest.mark.asyncio
async def test_ticket_search_route_returns_results():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="RouteQuery",
            Ticket_Body="Testing route order",
            Ticket_Contact_Name="Tester",
            Ticket_Contact_Email="tester@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()
        tid = t.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ticket/search", params={"q": "RouteQuery"})
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["Ticket_ID"] == tid for item in data)


@pytest.mark.asyncio
async def test_ticket_search_route_accepts_json():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="JsonQuery",
            Ticket_Body="Testing json input",
            Ticket_Contact_Name="Tester",
            Ticket_Contact_Email="tester@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()
        tid = t.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/ticket/search",
            json={"q": "JsonQuery", "limit": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["Ticket_ID"] == tid for item in data)
