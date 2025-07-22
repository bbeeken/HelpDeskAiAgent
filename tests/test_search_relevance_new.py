import pytest
from datetime import datetime, UTC

from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager
from src.enhanced_mcp_server import _search_tickets


@pytest.mark.asyncio
async def test_search_results_sorted_by_relevance():
    async with SessionLocal() as db:
        t1 = Ticket(
            Subject="Query Subject",
            Ticket_Body="body",
            Created_Date=datetime.now(UTC),
        )
        t2 = Ticket(
            Subject="Other",
            Ticket_Body="Contains query in body",
            Created_Date=datetime.now(UTC),
        )
        await TicketManager().create_ticket(db, t1)
        await TicketManager().create_ticket(db, t2)
        await db.commit()

    res = await _search_tickets("query", limit=5)
    assert res["status"] == "success"
    data = res["data"]
    assert len(data) >= 2
    assert data[0]["relevance"] >= data[1]["relevance"]
    assert "highlights" in data[0]
