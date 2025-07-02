import os
import asyncio
import pytest
from db.models import Base, Ticket
from db.mssql import engine, SessionLocal
from services.ticket_service import TicketService
from datetime import datetime, UTC
from tools.ticket_tools import create_ticket, search_tickets

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")


async def _setup_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.get_event_loop().run_until_complete(_setup_models())


@pytest.mark.asyncio
async def test_search_tickets():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Network issue",
            Ticket_Body="Cannot connect",
            Created_Date=datetime.now(UTC),
        )

        await create_ticket(db, t)
        results = await search_tickets(db, "Network")
        assert results and results[0].Subject == "Network issue"

