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
