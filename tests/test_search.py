import os

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from src.core.repositories.models import Base, Ticket
from src.infrastructure.database import engine, SessionLocal
from datetime import datetime, UTC
from src.core.services.ticket_management import TicketManager
from src.shared.schemas.search_params import TicketSearchParams
from src.core.repositories.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL
from httpx import AsyncClient, ASGITransport
from main import app


async def _setup_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
        await conn.exec_driver_sql(CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_models():
    await _setup_models()


@pytest.mark.asyncio
async def test_search_tickets():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Network issue",
            Ticket_Body="Cannot connect",
            Created_Date=datetime.now(UTC),
        )

        await TicketManager().create_ticket(db, t)
        await db.commit()
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
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/tickets/search", params={"q": "Bad"})
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_search_filters_escape_special_chars():
    async with SessionLocal() as db:
        t1 = Ticket(
            Subject="100% guaranteed",
            Ticket_Body="a",
            Created_Date=datetime.now(UTC),
        )
        t2 = Ticket(
            Subject="path\\to\\file",
            Ticket_Body="b",
            Created_Date=datetime.now(UTC),
        )
        t3 = Ticket(
            Subject="under_score_test",
            Ticket_Body="c",
            Created_Date=datetime.now(UTC),
        )
        await TicketManager().create_ticket(db, t1)
        await TicketManager().create_ticket(db, t2)
        await TicketManager().create_ticket(db, t3)
        await db.commit()

        params = TicketSearchParams(Subject="100% guaranteed")
        res = await TicketManager().search_tickets(db, "", params=params)
        assert any(r["Ticket_ID"] == t1.Ticket_ID for r in res)

        params = TicketSearchParams(Subject="path\\to\\file")
        res = await TicketManager().search_tickets(db, "", params=params)
        assert any(r["Ticket_ID"] == t2.Ticket_ID for r in res)

        params = TicketSearchParams(Subject="under_score_test")
        res = await TicketManager().search_tickets(db, "", params=params)
        assert any(r["Ticket_ID"] == t3.Ticket_ID for r in res)


@pytest.mark.asyncio
async def test_search_created_date_filters():
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

        params = TicketSearchParams(created_after=datetime(2023, 1, 5, tzinfo=UTC))
        res = await TicketManager().search_tickets(db, "DateFilter", params=params)
        ids = {r["Ticket_ID"] for r in res}
        assert ids == {new.Ticket_ID}

        params = TicketSearchParams(created_before=datetime(2023, 1, 5, tzinfo=UTC))
        res = await TicketManager().search_tickets(db, "DateFilter", params=params)
        ids = {r["Ticket_ID"] for r in res}
        assert ids == {old.Ticket_ID}
