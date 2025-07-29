import pytest
from contextlib import asynccontextmanager

import src.infrastructure.database as db
from src.core.services.ticket_management import TicketManager
from src.enhanced_mcp_server import (
    _create_ticket,
    _update_ticket,
)


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
    result = await _update_ticket(tid, {"Resolution": "done", "status": "closed"})
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
    result = await _update_ticket(tid, {"Assigned_Email": "tech@example.com"})
    assert result["status"] == "success"
    assert counter[0] == 1


@pytest.mark.asyncio
async def test_update_ticket_invalid_payload(monkeypatch):
    async with db.SessionLocal() as setup:
        ticket = {
            "Subject": "I",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "u",
            "Ticket_Contact_Email": "u@example.com",
        }
        res = await TicketManager().create_ticket(setup, ticket)
        await setup.commit()
        tid = res.data.Ticket_ID

    result = await _update_ticket(tid, {"bad_field": 1})
    assert result["status"] == "error"
