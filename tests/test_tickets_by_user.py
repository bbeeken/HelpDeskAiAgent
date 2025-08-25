import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC

from main import app
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket, TicketMessage, TicketStatus
from src.core.services.ticket_management import TicketManager
from src.mcp_server import create_enhanced_server


@pytest.mark.asyncio
async def test_get_tickets_by_user_function():
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        for sid, label in [(1, "Open"), (3, "Closed")]:
            if not await db.get(TicketStatus, sid):
                db.add(TicketStatus(ID=sid, Label=label))
        await db.commit()
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
        await TicketManager().create_ticket(db, t1)
        await TicketManager().create_ticket(db, t2)
        await TicketManager().create_ticket(db, t3)
        t4 = Ticket(
            Subject="D",
            Ticket_Body="b",
            Ticket_Status_ID=3,
            Ticket_Contact_Email="user@example.com",
            Created_Date=now,
        )
        await TicketManager().create_ticket(db, t4)
        await db.commit()
        msg = TicketMessage(
            Ticket_ID=t3.Ticket_ID,
            Message="hi",
            SenderUserCode="user@example.com",
            SenderUserName="User",
        )
        db.add(msg)
        await db.commit()
        res = await TicketManager().get_tickets_by_user(db, "USER@EXAMPLE.COM")
        ids = [r.Ticket_ID for r in res]
        assert ids == [t1.Ticket_ID, t2.Ticket_ID, t3.Ticket_ID, t4.Ticket_ID]

        t5 = Ticket(
            Subject="E",
            Ticket_Body="b",
            Ticket_Status_ID=1,
            Ticket_Contact_Email="user@example.com",
            Created_Date=now,
        )
        await TicketManager().create_ticket(db, t5)
        await db.commit()
        res = await TicketManager().get_tickets_by_user(db, "user@example.com")
        ids = [r.Ticket_ID for r in res]
        assert ids == [
            t1.Ticket_ID,
            t2.Ticket_ID,
            t3.Ticket_ID,
            t4.Ticket_ID,
            t5.Ticket_ID,
        ]

        limited = await TicketManager().get_tickets_by_user(db, "user@example.com", skip=1, limit=1)
        assert [t.Ticket_ID for t in limited] == [t2.Ticket_ID]
        closed_only = await TicketManager().get_tickets_by_user(
            db, "user@example.com", status="closed"
        )
        ids = {t.Ticket_ID for t in closed_only}
        assert ids == {t4.Ticket_ID}
        with pytest.raises(ValueError):
            await TicketManager().get_tickets_by_user(
                db, "user@example.com", status="bogus"
            )


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
            await TicketManager().create_ticket(db, t)
            await db.commit()
        resp = await ac.get("/ticket/by_user", params={"identifier": "endpoint@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [item["Ticket_ID"] for item in data["items"]]
        assert t.Ticket_ID in ids

        async with SessionLocal() as db:
            t_new = Ticket(
                Subject="E2",
                Ticket_Body="b",
                Ticket_Status_ID=1,
                Ticket_Contact_Name="U2",
                Ticket_Contact_Email="endpoint@example.com",
                Created_Date=now,
            )
            await TicketManager().create_ticket(db, t_new)
            await db.commit()
        resp = await ac.get("/ticket/by_user", params={"identifier": "endpoint@example.com"})
        ids = [item["Ticket_ID"] for item in resp.json()["items"]]
        assert t_new.Ticket_ID in ids


@pytest.mark.asyncio
async def test_invalid_status_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/ticket/by_user",
            params={"identifier": "endpoint@example.com", "status": "bogus"},
        )
        assert resp.status_code == 400


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
        await TicketManager().create_ticket(db, t)
        await db.commit()

    server = create_enhanced_server()
    tool = next(x for x in server._tools if x.name == "search_tickets")
    res = await tool._implementation(user="tool@example.com")
    assert res["status"] == "success"
    ids = {r["Ticket_ID"] for r in res.get("data", [])}
    assert ids == {t.Ticket_ID}

    async with SessionLocal() as db:
        t2 = Ticket(
            Subject="Tool2",
            Ticket_Body="b",
            Ticket_Status_ID=1,
            Ticket_Contact_Name="T2",
            Ticket_Contact_Email="tool@example.com",
            Created_Date=now,
        )
        await TicketManager().create_ticket(db, t2)
        await db.commit()
    res = await tool._implementation(user="tool@example.com")
    ids = {r["Ticket_ID"] for r in res.get("data", [])}
    assert ids == {t.Ticket_ID, t2.Ticket_ID}


@pytest.mark.asyncio
async def test_status_and_filtering():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        now = datetime.now(UTC)
        async with SessionLocal() as db:
            for sid, label in [(1, "Open"), (3, "Closed")]:
                if not await db.get(TicketStatus, sid):
                    db.add(TicketStatus(ID=sid, Label=label))
            await db.commit()
            open_t = Ticket(
                Subject="OpenF",
                Ticket_Body="b",
                Ticket_Status_ID=1,
                Ticket_Contact_Email="filter@example.com",
                Site_ID=1,
                Created_Date=now,
            )
            closed_t = Ticket(
                Subject="ClosedF",
                Ticket_Body="b",
                Ticket_Status_ID=3,
                Ticket_Contact_Email="filter@example.com",
                Site_ID=2,
                Created_Date=now,
            )
            await TicketManager().create_ticket(db, open_t)
            await TicketManager().create_ticket(db, closed_t)
            await db.commit()

        resp = await ac.get(
            "/ticket/by_user",
            params={"identifier": "filter@example.com", "status": "closed"},
        )
        assert resp.status_code == 200
        ids = [i["Ticket_ID"] for i in resp.json()["items"]]
        assert ids == [closed_t.Ticket_ID]

        resp = await ac.get(
            "/ticket/by_user",
            params={"identifier": "filter@example.com", "Site_ID": 1},
        )
        assert resp.status_code == 200
        ids = [i["Ticket_ID"] for i in resp.json()["items"]]
        assert ids == [open_t.Ticket_ID]

    server = create_enhanced_server()
    tool = next(x for x in server._tools if x.name == "search_tickets")
    res = await tool._implementation(
        user="filter@example.com", filters={"status": "closed"}
    )
    ids = {r["Ticket_ID"] for r in res.get("data", [])}
    assert ids == {closed_t.Ticket_ID}
    res = await tool._implementation(
        user="filter@example.com", filters={"Site_ID": 1}
    )
    ids = {r["Ticket_ID"] for r in res.get("data", [])}
    assert ids == {open_t.Ticket_ID}
