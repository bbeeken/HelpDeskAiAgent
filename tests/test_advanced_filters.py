import pytest
from datetime import datetime, UTC

from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager
from src.shared.schemas.filters import AdvancedFilters


@pytest.mark.asyncio
async def test_date_range_and_sort():
    async with SessionLocal() as db:
        t1 = Ticket(
            Subject="A",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime(2023, 1, 1, tzinfo=UTC),
        )
        t2 = Ticket(
            Subject="B",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime(2023, 1, 10, tzinfo=UTC),
        )
        await TicketManager().create_ticket(db, t1)
        await TicketManager().create_ticket(db, t2)

        filters = AdvancedFilters(
            created_from=datetime(2023, 1, 5, tzinfo=UTC),
            sort=["-Created_Date"],
        )
        res = await TicketManager().list_tickets(db, filters=filters)
        ids = [r.Ticket_ID for r in res]
        assert ids == [t2.Ticket_ID]


@pytest.mark.asyncio
async def test_multi_value_and_bool_filter():
    async with SessionLocal() as db:
        t1 = Ticket(
            Subject="C",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Site_ID=1,
            Created_Date=datetime.now(UTC),
        )
        t2 = Ticket(
            Subject="D",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Site_ID=2,
            Assigned_Email="tech@example.com",
            Created_Date=datetime.now(UTC),
        )
        await TicketManager().create_ticket(db, t1)
        await TicketManager().create_ticket(db, t2)
        filters = AdvancedFilters(site_ids=[1, 2], assigned=False)
        res = await TicketManager().list_tickets(db, filters=filters)
        ids = {t.Ticket_ID for t in res}
        assert ids == {t1.Ticket_ID}
