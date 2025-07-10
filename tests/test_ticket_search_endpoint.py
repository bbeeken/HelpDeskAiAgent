import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC

from main import app
from db.mssql import SessionLocal
from db.models import Ticket
from tools.ticket_tools import create_ticket


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
        await create_ticket(db, t)
        tid = t.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ticket/search", params={"q": "RouteQuery"})
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["Ticket_ID"] == tid for item in data)
