import asyncio
from datetime import datetime, UTC

import pytest

from src.core.services.ticket_management import TicketManager
from src.core.repositories.models import Ticket
from src.infrastructure.database import SessionLocal


@pytest.mark.asyncio
async def test_update_ticket_ignores_restricted_fields():
    async with SessionLocal() as db:
        created = datetime(2024, 1, 1, tzinfo=UTC)
        ticket = Ticket(
            Subject="Restricted",
            Ticket_Body="body",
            Ticket_Contact_Name="User",
            Ticket_Contact_Email="user@example.com",
            Created_Date=created,
            Ticket_Status_ID=1,
        )
        result = await TicketManager().create_ticket(db, ticket)
        await db.commit()
        tid = result.data.Ticket_ID
        orig_created = result.data.Created_Date
        orig_closed = result.data.Closed_Date
        orig_last = result.data.LastModified

        await asyncio.sleep(0.01)
        updates = {
            "Subject": "Updated",
            "Created_Date": datetime(2000, 1, 1, tzinfo=UTC),
            "Closed_Date": datetime(2000, 1, 2, tzinfo=UTC),
            "LastModified": datetime(2000, 1, 3, tzinfo=UTC),
        }
        updated = await TicketManager().update_ticket(db, tid, updates)
        await db.commit()

        assert updated.Subject == "Updated"
        assert updated.Created_Date == orig_created
        assert updated.Closed_Date == orig_closed
        assert updated.LastModified > orig_last
        assert updated.LastModified != updates["LastModified"]

        refreshed = await TicketManager().get_ticket(db, tid)
        assert refreshed.Created_Date == orig_created
        assert refreshed.Closed_Date == orig_closed
        assert refreshed.LastModified == updated.LastModified
