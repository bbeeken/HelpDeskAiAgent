import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC

from main import app
from db.mssql import SessionLocal
from db.models import Ticket, TicketMessage
from tools.ticket_tools import create_ticket, get_tickets_by_user
from src.mcp_server import create_enhanced_server

@pytest.mark.asyncio
async def test_get_tickets_by_user_function():
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        t1 = Ticket(
            Subject="A",
            Ticket_Body="b",
            Ticket_Status_ID=1,
            Ticket_Contact_Name="X",
            Ticket_Contact_Email="user@example.com",
            Created_Date=now,
        )
        t2 = Ticket(
            Subject="B",
            Ticket_Body="b",
            Ticket_Status_ID=1,
            Ticket_Contact_Name="Y",
            Ticket_Contact_Email="y@example.com",
            Assigned_Email="user@example.com",
            Created_Date=now,
        )
        t3 = Ticket(
            Subject="C",
            Ticket_Body="b",
            Ticket_Status_ID=1,
            Ticket_Contact_Name="Z",
            Ticket_Contact_Email="z@example.com",
            Created_Date=now,
        )
        await create_ticket(db, t1)
        await create_ticket(db, t2)
        await create_ticket(db, t3)
        msg = TicketMessage(
            Ticket_ID=t3.Ticket_ID,
            Message="hi",
            SenderUserCode="user@example.com",
            SenderUserName="User",
            DateTimeStamp=now,
        )
        db.add(msg)
        await db.commit()
        res = await get_tickets_by_user(db, "USER@EXAMPLE.COM")
        ids = {r.Ticket_ID for r in res}
        assert ids == {t1.Ticket_ID, t2.Ticket_ID, t3.Ticket_ID}
        limited = await get_tickets_by_user(db, "user@example.com", skip=1, limit=1)
        assert len(limited) == 1


@pytest.mark.asyncio
async def test_tickets_by_user_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        now = datetime.now(UTC)
        async with SessionLocal() as db:
            t = Ticket(
                Subject="E",
                Ticket_Body="b",
                Ticket_Status_ID=1,
                Ticket_Contact_Name="U",
                Ticket_Contact_Email="endpoint@example.com",
                Created_Date=now,
            )
            await create_ticket(db, t)
        resp = await ac.get("/tickets/by_user", params={"identifier": "endpoint@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [item["Ticket_ID"] for item in data["items"]]
        assert t.Ticket_ID in ids


@pytest.mark.asyncio
async def test_tickets_by_user_tool():
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Tool",
            Ticket_Body="b",
            Ticket_Status_ID=1,
            Ticket_Contact_Name="T",
            Ticket_Contact_Email="tool@example.com",
            Created_Date=now,
        )
        await create_ticket(db, t)

    server = create_enhanced_server()
    tool = next(x for x in server._tools if x.name == "tickets_by_user")
    res = await tool._implementation(identifier="tool@example.com")
    ids = {r.Ticket_ID for r in res}
    assert t.Ticket_ID in ids
