import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import text

import src.infrastructure.database as db
from src.core.services.ticket_management import TicketManager
from src.enhanced_mcp_server import (
    _create_ticket,
    _update_ticket,
)
from src.shared.utils.date_format import parse_db_datetime


async def _patched_session(monkeypatch, commit_counter):
    real_sessionmaker = db.SessionLocal

    @asynccontextmanager
    async def _factory():
        async with real_sessionmaker() as session:
            orig = session.commit

            async def commit_wrapper():
                commit_counter[0] += 1
                await orig()

            monkeypatch.setattr(session, "commit", commit_wrapper)
            yield session

    monkeypatch.setattr(db, "SessionLocal", _factory)


@pytest.mark.asyncio
async def test_create_ticket_commits_once(monkeypatch):
    counter = [0]
    await _patched_session(monkeypatch, counter)
    payload = {
        "Subject": "Test",
        "Ticket_Body": "body",
        "Ticket_Contact_Name": "User",
        "Ticket_Contact_Email": "user@example.com",
    }
    result = await _create_ticket(**payload)
    assert result["status"] == "success"
    assert counter[0] == 1


@pytest.mark.asyncio
async def test_update_ticket_commits_once(monkeypatch):
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "U",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    counter = [0]
    await _patched_session(monkeypatch, counter)
    updates = {"Subject": "New"}
    result = await _update_ticket(tid, updates)
    assert result["status"] == "success"
    assert counter[0] == 1


@pytest.mark.asyncio
async def test_close_ticket_commits_once(monkeypatch):
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "C",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    counter = [0]
    await _patched_session(monkeypatch, counter)
    result = await _update_ticket(tid, {"resolution": "done", "status": "closed"})
    assert result["status"] == "success"
    assert result["data"]["Ticket_Status_ID"] == 3
    assert counter[0] == 1


@pytest.mark.asyncio
async def test_assign_ticket_commits_once(monkeypatch):
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "A",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    counter = [0]
    await _patched_session(monkeypatch, counter)
    result = await _update_ticket(tid, {"assignee_email": "tech@example.com"})
    assert result["status"] == "success"
    assert counter[0] == 1


@pytest.mark.asyncio
async def test_assign_ticket_semantic_fields(monkeypatch):
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "A2",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    counter = [0]
    await _patched_session(monkeypatch, counter)
    result = await _update_ticket(
        tid,
        {"assignee_email": "tech@example.com", "assignee_name": "Tech"},
    )
    assert result["status"] == "success"
    assert counter[0] == 1
    data = result["data"]
    assert data["Assigned_Email"] == "tech@example.com"
    assert data["Assigned_Name"] == "Tech"


@pytest.mark.asyncio
async def test_update_ticket_empty_updates(monkeypatch):
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "E1",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    result = await _update_ticket(tid, {})
    assert result["status"] == "error"
    err = result["error"]
    if isinstance(err, dict):
        err_msg = err.get("message", "")
    else:
        err_msg = err
    assert "No updates" in err_msg


@pytest.mark.asyncio
async def test_update_ticket_unknown_status():
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "S1",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    result = await _update_ticket(tid, {"status": "bogus"})
    assert result["status"] == "error"
    err = result["error"]
    if isinstance(err, dict):
        err_msg = err.get("message", "")
    else:
        err_msg = err
    assert "Unknown" in err_msg


@pytest.mark.asyncio
async def test_update_ticket_ambiguous_priority():
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "P1",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    result = await _update_ticket(tid, {"priority": [1, "low"]})
    assert result["status"] == "error"
    err = result["error"]
    if isinstance(err, dict):
        err_msg = err.get("message", "")
    else:
        err_msg = err
    assert "Ambiguous" in err_msg


@pytest.mark.asyncio
async def test_update_ticket_unknown_priority():
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "P2",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    result = await _update_ticket(tid, {"priority": "urgent"})
    assert result["status"] == "error"
    err = result["error"]
    if isinstance(err, dict):
        err_msg = err.get("message", "")
    else:
        err_msg = err
    assert "Unknown" in err_msg


@pytest.mark.asyncio
async def test_timezone_aware_creation_ms_precision():
    aware = datetime(2024, 1, 2, 3, 4, 5, 987654, tzinfo=timezone.utc)
    async with db.SessionLocal() as session:
        ticket = {
            "Subject": "TZ",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
            "Created_Date": aware,
            "Closed_Date": aware,
        }
        res = await TicketManager().create_ticket(session, ticket)
        assert res.success
        await session.commit()
        tid = res.data.Ticket_ID

    async with db.SessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT Created_Date, Closed_Date FROM Tickets_Master WHERE Ticket_ID=:id"
            ),
            {"id": tid},
        )
        created_raw, closed_raw = result.one()

    for raw in (created_raw, closed_raw):
        frac = raw.split(".")[1]
        assert len(frac) == 3
        parsed = parse_db_datetime(raw)
        assert parsed.microsecond % 1000 == 0

    assert parse_db_datetime(created_raw) == aware.replace(
        microsecond=(aware.microsecond // 1000) * 1000
    )
