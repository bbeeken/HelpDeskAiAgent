import pytest
from datetime import datetime, UTC

from db.mssql import SessionLocal
from db.models import Ticket
from tools.ticket_management import TicketManager
from tools.analytics_reporting import tickets_by_status
from tools.operation_result import OperationResult


@pytest.mark.asyncio
async def test_create_ticket_returns_operation_result():
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="OpRes",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        result = await TicketManager().create_ticket(db, ticket)
        assert isinstance(result, OperationResult)
        assert result.success
        assert isinstance(result.data, Ticket)


@pytest.mark.asyncio
async def test_tickets_by_status_failure(monkeypatch):
    async with SessionLocal() as db:
        async def fail_execute(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(db, "execute", fail_execute)
        result = await tickets_by_status(db)
        assert isinstance(result, OperationResult)
        assert not result.success
        assert result.error
