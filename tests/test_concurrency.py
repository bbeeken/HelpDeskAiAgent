from datetime import datetime, UTC
from src.core.repositories.models import Ticket
from src.infrastructure.database import SessionLocal
from src.core.services.ticket_management import TicketManager
import asyncio
import httpx
from httpx import ASGITransport
from main import app


async def _add_sample_ticket():
    async with SessionLocal() as session:
        t = Ticket(
            Subject="Net",
            Ticket_Body="Conn",
            Ticket_Contact_Name="T",
            Ticket_Contact_Email="t@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(session, t)
        await session.commit()


async def _search_worker():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ticket/search", params={"q": "Net"})
        return resp.json()[0]["Subject"]


async def _analytics_worker():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/analytics/status")
        return resp.json()[0]["count"]


import pytest


@pytest.mark.asyncio
async def test_concurrent_search():
    await _add_sample_ticket()
    tasks = [asyncio.create_task(_search_worker()) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    assert all(r == "Net" for r in results)


@pytest.mark.asyncio
async def test_concurrent_analytics():
    await _add_sample_ticket()
    tasks = [asyncio.create_task(_analytics_worker()) for _ in range(5)]
    counts = await asyncio.gather(*tasks)
    assert all(c >= 1 for c in counts)
