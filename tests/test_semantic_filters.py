import pytest
from datetime import datetime, UTC

from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket, TicketStatus
from src.core.services.ticket_management import TicketManager
from src.core.services.ticket_management import (
    apply_semantic_filters,
    _apply_semantic_filters,
    _OPEN_STATE_IDS,
    _CLOSED_STATE_IDS,
)


@pytest.mark.asyncio
async def test_open_status_filter_matches_multiple_states():
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        statuses = [
            (1, "Open"),
            (2, "In Progress"),
            (3, "Closed"),
            (4, "Waiting"),
        ]
        for sid, label in statuses:
            if not await db.get(TicketStatus, sid):
                db.add(TicketStatus(ID=sid, Label=label))
        await db.commit()

        t1 = Ticket(Subject="A", Ticket_Body="b", Created_Date=now, Ticket_Status_ID=1)
        t2 = Ticket(Subject="B", Ticket_Body="b", Created_Date=now, Ticket_Status_ID=2)
        t3 = Ticket(Subject="C", Ticket_Body="b", Created_Date=now, Ticket_Status_ID=3)
        t4 = Ticket(Subject="D", Ticket_Body="b", Created_Date=now, Ticket_Status_ID=4)

        for t in (t1, t2, t3, t4):
            await TicketManager().create_ticket(db, t)
        await db.commit()

        filters = _apply_semantic_filters({"status": "open"})
        assert filters == {"Ticket_Status_ID": _OPEN_STATE_IDS}

        res = await TicketManager().list_tickets(db, filters=filters)
        ids = {t.Ticket_ID for t in res}
        assert ids == {t1.Ticket_ID, t2.Ticket_ID, t4.Ticket_ID}


@pytest.mark.asyncio
async def test_priority_filter_maps_to_severity_id():
    filters = apply_semantic_filters({"priority": "high"})
    assert filters == {"Severity_ID": 2}

    filters = apply_semantic_filters({"priority": 3})
    assert filters == {"Severity_ID": 3}

    filters = apply_semantic_filters({"priority": [1, "low"]})
    assert filters == {"Severity_ID": [1, 4]}


def test_status_string_mappings():
    mapping_expectations = {
        "open": _OPEN_STATE_IDS,
        "closed": _CLOSED_STATE_IDS,
        "in_progress": 2,
        "progress": 2,
        "pending": 3,
        "resolved": 4,
    }
    for status, expected in mapping_expectations.items():
        result = _apply_semantic_filters({"status": status})
        assert result == {"Ticket_Status_ID": expected}


def test_open_closed_constants():
    assert _OPEN_STATE_IDS == [1, 2, 4, 5, 6, 8]
    assert _CLOSED_STATE_IDS == [3]
