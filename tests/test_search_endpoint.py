from datetime import datetime, UTC

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager


@pytest.mark.asyncio
async def test_search_returns_long_ticket_body():
    async with SessionLocal() as db:
        valid = Ticket(
            Subject="Query",
            Ticket_Body="valid",
            Ticket_Contact_Name="T",
            Ticket_Contact_Email="t@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        invalid = Ticket(
            Subject="Query",
            Ticket_Body="x" * 2100,
            Ticket_Contact_Name="T",
            Ticket_Contact_Email="t@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, valid)
        await TicketManager().create_ticket(db, invalid)
        await db.commit()
        valid_id = valid.Ticket_ID
        invalid_id = invalid.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ticket/search", params={"q": "Query"})
        assert resp.status_code == 200
        data = resp.json()
        ids = {item["Ticket_ID"] for item in data}
        assert {valid_id, invalid_id} <= ids
        for item in data:
            assert set(["Ticket_ID", "Subject", "body_preview",
                       "status_label", "priority_level"]).issubset(item.keys())


@pytest.mark.asyncio
async def test_search_filters_and_sort():
    async with SessionLocal() as db:
        first = Ticket(
            Subject="Query",
            Ticket_Body="one",
            Ticket_Contact_Name="T",
            Ticket_Contact_Email="t@example.com",
            Created_Date=datetime(2023, 1, 1, tzinfo=UTC),
            Ticket_Status_ID=1,
            Site_ID=1,
        )
        second = Ticket(
            Subject="Query",
            Ticket_Body="two",
            Ticket_Contact_Name="T",
            Ticket_Contact_Email="t@example.com",
            Created_Date=datetime(2023, 1, 2, tzinfo=UTC),
            Ticket_Status_ID=1,
            Site_ID=2,
        )
        await TicketManager().create_ticket(db, first)
        await TicketManager().create_ticket(db, second)
        await db.commit()
        first_id = first.Ticket_ID
        second_id = second.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/ticket/search",
            params={"q": "Query", "Site_ID": 1, "Ticket_Status_ID": 1, "sort": "oldest"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1 and data[0]["Ticket_ID"] == first_id

        resp = await ac.get("/ticket/search", params={"q": "Query", "sort": "oldest"})
        ids = [item["Ticket_ID"] for item in resp.json()]
        assert ids == [first_id, second_id]


@pytest.mark.asyncio
async def test_search_accepts_json():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="JSON Search",
            Ticket_Body="json body",
            Ticket_Contact_Name="T",
            Ticket_Contact_Email="t@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()
        tid = t.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/ticket/search", json={"q": "JSON Search"})
        assert resp.status_code == 200
        ids = [item["Ticket_ID"] for item in resp.json()]
        assert tid in ids


@pytest.mark.asyncio
async def test_search_created_date_filters_endpoint():
    async with SessionLocal() as db:
        old = Ticket(
            Subject="DateFilter",
            Ticket_Body="old",
            Created_Date=datetime(2023, 1, 1, tzinfo=UTC),
            Ticket_Status_ID=1,
        )
        new = Ticket(
            Subject="DateFilter",
            Ticket_Body="new",
            Created_Date=datetime(2023, 1, 10, tzinfo=UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, old)
        await TicketManager().create_ticket(db, new)
        await db.commit()
        old_id = old.Ticket_ID
        new_id = new.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/ticket/search",
            params={"q": "DateFilter", "created_after": "2023-01-05T00:00:00+00:00"},
        )
        assert resp.status_code == 200
        ids = {item["Ticket_ID"] for item in resp.json()}
        assert ids == {new_id}

        resp = await ac.post(
            "/ticket/search",
            json={
                "q": "DateFilter",
                "params": {"created_before": "2023-01-05T00:00:00+00:00"},
            },
        )
        assert resp.status_code == 200
        ids = {item["Ticket_ID"] for item in resp.json()}
        assert ids == {old_id}
