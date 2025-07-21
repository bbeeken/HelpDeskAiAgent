import asyncio
from datetime import datetime, UTC
import httpx
from httpx import ASGITransport
from main import app
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager
import src.core.services.analytics_reporting as ar
import pytest


async def _add_sample_ticket():
    async with SessionLocal() as session:
        t = Ticket(
            Subject="Cache",
            Ticket_Body="Body",
            Ticket_Contact_Name="C",
            Ticket_Contact_Email="c@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(session, t)


def _enable_cache(monkeypatch):
    monkeypatch.setattr(ar, "_cache_enabled", True)
    ar._analytics_cache.clear()


async def _analytics_worker():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/analytics/status")
        return resp.json()[0]["count"]


@pytest.mark.asyncio
async def test_concurrent_cached_analytics(monkeypatch):
    _enable_cache(monkeypatch)
    await _add_sample_ticket()
    tasks = [asyncio.create_task(_analytics_worker()) for _ in range(10)]
    counts = await asyncio.gather(*tasks)
    assert all(c >= 1 for c in counts)
