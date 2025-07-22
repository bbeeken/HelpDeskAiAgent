import pytest
from datetime import datetime, UTC

from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager
from src.enhanced_mcp_server import _list_tickets


@pytest.mark.asyncio
async def test_semantic_status_filter():
    async with SessionLocal() as db:
        open_t = Ticket(
            Subject="OpenTicket",
            Ticket_Body="b",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        closed_t = Ticket(
            Subject="ClosedTicket",
            Ticket_Body="b",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=4,
        )
        await TicketManager().create_ticket(db, open_t)
        await TicketManager().create_ticket(db, closed_t)
        await db.commit()

    res = await _list_tickets(limit=10, filters={"status": "open"})
    assert res["status"] == "success"
    ids = {t["Ticket_ID"] for t in res["data"]}
    assert open_t.Ticket_ID in ids
    assert closed_t.Ticket_ID not in ids
