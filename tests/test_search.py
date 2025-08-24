import os

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from src.core.repositories.models import Base, Ticket
from src.infrastructure.database import engine, SessionLocal
from datetime import datetime, UTC, timedelta
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
        records, _ = await TicketManager().search_tickets(db, "Network", params=params)
        assert records and records[0].Subject == "Network issue"
        assert hasattr(records[0], "Ticket_ID")


@pytest.mark.asyncio
async def test_search_endpoint_handles_long_ticket_body():
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
        bad_id = bad.Ticket_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/tickets/search", params={"q": "Bad"})
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["Ticket_ID"] == bad_id for item in data)


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
        res, _ = await TicketManager().search_tickets(db, "", params=params)
        assert any(r.Ticket_ID == t1.Ticket_ID for r in res)

        params = TicketSearchParams(Subject="path\\to\\file")
        res, _ = await TicketManager().search_tickets(db, "", params=params)
        assert any(r.Ticket_ID == t2.Ticket_ID for r in res)

        params = TicketSearchParams(Subject="under_score_test")
        res, _ = await TicketManager().search_tickets(db, "", params=params)
        assert any(r.Ticket_ID == t3.Ticket_ID for r in res)


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
        res, _ = await TicketManager().search_tickets(db, "DateFilter", params=params)
        ids = {r.Ticket_ID for r in res}
        assert ids == {new.Ticket_ID}

        params = TicketSearchParams(created_before=datetime(2023, 1, 5, tzinfo=UTC))
        res, _ = await TicketManager().search_tickets(db, "DateFilter", params=params)
        ids = {r.Ticket_ID for r in res}
        assert ids == {old.Ticket_ID}


@pytest.mark.asyncio
async def test_search_created_after_string_precision():
    async with SessionLocal() as db:
        old = Ticket(
            Subject="DatePrecision",
            Ticket_Body="old",
            Created_Date=datetime(2023, 1, 1, tzinfo=UTC),
            Ticket_Status_ID=1,
        )
        new = Ticket(
            Subject="DatePrecision",
            Ticket_Body="new",
            Created_Date=datetime(2023, 1, 10, tzinfo=UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, old)
        await TicketManager().create_ticket(db, new)
        await db.commit()

        res, _ = await TicketManager().search_tickets(
            db,
            "DatePrecision",
            created_after="2023-01-05T00:00:00.123456+00:00",
        )
        ids = {r.Ticket_ID for r in res}
        assert ids == {new.Ticket_ID}


@pytest.mark.asyncio
async def test_search_created_after_invalid_string():
    async with SessionLocal() as db:
        with pytest.raises(ValueError):
            await TicketManager().search_tickets(db, "x", created_after="bad")


@pytest.mark.asyncio
async def test_search_datetime_and_days_filters():
    async with SessionLocal() as db:
        old = Ticket(
            Subject="MicroDate",
            Ticket_Body="old",
            Created_Date=datetime.now(UTC) - timedelta(days=5),
            Ticket_Status_ID=1,
        )
        new = Ticket(
            Subject="MicroDate",
            Ticket_Body="new",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, old)
        await TicketManager().create_ticket(db, new)
        await db.commit()

        after = datetime.now(UTC) - timedelta(days=2, microseconds=987654)
        res, _ = await TicketManager().search_tickets(
            db,
            "MicroDate",
            created_after=after,
        )
        assert {r.Ticket_ID for r in res} == {new.Ticket_ID}

        res, _ = await TicketManager().search_tickets(db, "MicroDate", days=2)
        assert {r.Ticket_ID for r in res} == {new.Ticket_ID}


@pytest.mark.asyncio
async def test_search_days_none_returns_all():
    async with SessionLocal() as db:
        old = Ticket(
            Subject="DayNone",
            Ticket_Body="old",
            Created_Date=datetime.now(UTC) - timedelta(days=5),
            Ticket_Status_ID=1,
        )
        new = Ticket(
            Subject="DayNone",
            Ticket_Body="new",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, old)
        await TicketManager().create_ticket(db, new)
        await db.commit()

        res, _ = await TicketManager().search_tickets(db, "DayNone", days=None)
        assert {r.Ticket_ID for r in res} == {old.Ticket_ID, new.Ticket_ID}


@pytest.mark.asyncio
async def test_search_days_zero_returns_all():
    async with SessionLocal() as db:
        old = Ticket(
            Subject="DayZero",
            Ticket_Body="old",
            Created_Date=datetime.now(UTC) - timedelta(days=5),
            Ticket_Status_ID=1,
        )
        new = Ticket(
            Subject="DayZero",
            Ticket_Body="new",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, old)
        await TicketManager().create_ticket(db, new)
        await db.commit()

        res, _ = await TicketManager().search_tickets(db, "DayZero", days=0)
        assert {r.Ticket_ID for r in res} == {old.Ticket_ID, new.Ticket_ID}


@pytest.mark.asyncio
async def test_search_days_invalid_value():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="BadDays",
            Ticket_Body="body",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()

        with pytest.raises(ValueError):
            await TicketManager().search_tickets(db, "BadDays", days="oops")
