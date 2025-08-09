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
    _STATUS_MAP,

)


@pytest.mark.asyncio
async def test_open_status_filter_matches_multiple_states():
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        statuses = [
            ("1", "Open"),
            ("2", "In Progress"),
            ("3", "Closed"),
            ("4", "Waiting"),
        ]
        for sid, label in statuses:
            if not await db.get(TicketStatus, sid):
                db.add(TicketStatus(ID=sid, Label=label))
        await db.commit()

        t1 = Ticket(Subject="A", Ticket_Body="b", Created_Date=now, Ticket_Status_ID="1")
        t2 = Ticket(Subject="B", Ticket_Body="b", Created_Date=now, Ticket_Status_ID="2")
        t3 = Ticket(Subject="C", Ticket_Body="b", Created_Date=now, Ticket_Status_ID="3")
        t4 = Ticket(Subject="D", Ticket_Body="b", Created_Date=now, Ticket_Status_ID="4")

        for t in (t1, t2, t3, t4):
            await TicketManager().create_ticket(db, t)
        await db.commit()

        filters = _apply_semantic_filters({"status": "open"})
        assert filters == {"Ticket_Status_ID": _OPEN_STATE_IDS}

        res = await TicketManager().list_tickets(db, filters=filters)
        ids = {t.Ticket_ID for t in res}
        assert ids == {t1.Ticket_ID, t2.Ticket_ID, t4.Ticket_ID}


@pytest.mark.asyncio
async def test_closed_status_filter_maps_to_multiple_ids():
    filters = apply_semantic_filters({"status": "closed"})
    assert filters == {"Ticket_Status_ID": _CLOSED_STATE_IDS}


@pytest.mark.asyncio
async def test_in_progress_status_expands_all_ids():
    filters = apply_semantic_filters({"status": "in_progress"})
    assert filters == {"Ticket_Status_ID": _STATUS_MAP["in_progress"]}


@pytest.mark.asyncio
async def test_priority_filter_maps_to_severity_id():
    filters = apply_semantic_filters({"priority": "high"})
    assert filters == {"Severity_ID": 2}

    filters = apply_semantic_filters({"priority": 3})
    assert filters == {"Severity_ID": 3}

    filters = apply_semantic_filters({"priority": [1, "low"]})
    assert filters == {"Severity_ID": [1, 4]}


@pytest.mark.asyncio
async def test_assignee_email_and_name_filters():
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        t1 = Ticket(
            Subject="F1",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e",
            Assigned_Email="tech@example.com",
            Assigned_Name="Tech",
            Ticket_Status_ID="1",
            Created_Date=now,
        )
        t2 = Ticket(
            Subject="F2",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e",
            Assigned_Email="other@example.com",
            Assigned_Name="Other",
            Ticket_Status_ID="1",
            Created_Date=now,
        )
        await TicketManager().create_ticket(db, t1)
        await TicketManager().create_ticket(db, t2)
        await db.commit()

        filters = apply_semantic_filters({"assignee_email": "tech@example.com"})
        assert filters == {"Assigned_Email": "tech@example.com"}
        res = await TicketManager().list_tickets(db, filters=filters)
        ids = {t.Ticket_ID for t in res}
        assert ids == {t1.Ticket_ID}

        filters = apply_semantic_filters({"assignee_name": "Tech"})
        assert filters == {"Assigned_Name": "Tech"}
        res = await TicketManager().list_tickets(db, filters=filters)
        ids = {t.Ticket_ID for t in res}
        assert ids == {t1.Ticket_ID}


def test_status_string_mappings():
    mapping_expectations = {
        "open": _OPEN_STATE_IDS,
        "closed": _CLOSED_STATE_IDS,
        "in_progress": ["2", "5"],
        "progress": ["2", "5"],
        "pending": "6",
        "resolved": _STATUS_MAP["resolved"],
    }
    for status, expected in mapping_expectations.items():
        result = _apply_semantic_filters({"status": status})
        assert result == {"Ticket_Status_ID": expected}


def test_open_closed_constants():
    assert _OPEN_STATE_IDS == ["1", "2", "4", "5", "6", "8"]
    assert _CLOSED_STATE_IDS == ["3"]


def test_status_filter_unknown_value():
    with pytest.raises(ValueError) as exc:
        apply_semantic_filters({"status": "bogus"})
    err = exc.value.args[0]
    assert isinstance(err, dict)
    assert err["field"] == "status"
    assert "Unknown" in err["message"]


def test_priority_filter_unknown_value():
    with pytest.raises(ValueError) as exc:
        apply_semantic_filters({"priority": "urgent"})
    err = exc.value.args[0]
    assert isinstance(err, dict)
    assert err["field"] in {"priority", "priority_level"}
    assert "Unknown" in err["message"]
