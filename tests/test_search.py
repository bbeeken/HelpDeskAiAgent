import os
import asyncio
import pytest
from src.core.repositories.models import Base, Ticket
from src.infrastructure.database import engine, SessionLocal
from datetime import datetime, UTC
from src.core.services.ticket_management import TicketManager
from src.shared.schemas.search_params import TicketSearchParams
from src.core.repositories.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL
from httpx import AsyncClient, ASGITransport
from main import app

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")


async def _setup_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
        await conn.exec_driver_sql(CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL)

asyncio.get_event_loop().run_until_complete(_setup_models())


@pytest.mark.asyncio
async def test_search_tickets():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Network issue",
            Ticket_Body="Cannot connect",
            Created_Date=datetime.now(UTC),
        )

        await TicketManager().create_ticket(db, t)
        params = TicketSearchParams()
        results = await TicketManager().search_tickets(db, "Network", params=params)
        assert results and results[0]["Subject"] == "Network issue"
        assert "body_preview" in results[0]


@pytest.mark.asyncio
async def test_search_endpoint_skips_invalid_ticket():
    async with SessionLocal() as db:
        bad = Ticket(
            Subject="Bad",
            Ticket_Body="x" * 2001,
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, bad)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/tickets/search", params={"q": "Bad"})
        assert resp.status_code == 200
        assert resp.json() == []
