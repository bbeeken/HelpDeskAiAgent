from datetime import datetime, UTC

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from db.mssql import SessionLocal
from db.models import Ticket
from tools.ticket_tools import create_ticket


@pytest.mark.asyncio
async def test_search_skips_oversized_ticket_body():
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
        await create_ticket(db, valid)
        await create_ticket(db, invalid)
        valid_id = valid.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/tickets/search", params={"q": "Query"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["Ticket_ID"] == valid_id
        assert set(["Ticket_ID", "Subject", "body_preview", "status_label", "priority_level"]) <= item.keys()


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
        await create_ticket(db, first)
        await create_ticket(db, second)
        first_id = first.Ticket_ID
        second_id = second.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/tickets/search",
            params={"q": "Query", "Site_ID": 1, "Ticket_Status_ID": 1, "sort": "oldest"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1 and data[0]["Ticket_ID"] == first_id

        resp = await ac.get("/tickets/search", params={"q": "Query", "sort": "oldest"})
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
        await create_ticket(db, t)
        tid = t.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/tickets/search", json={"q": "JSON Search"})
        assert resp.status_code == 200
        ids = [item["Ticket_ID"] for item in resp.json()]
        assert tid in ids
