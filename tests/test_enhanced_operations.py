import pytest
from datetime import datetime, UTC

from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services import TicketManager, EnhancedOperationsManager


@pytest.mark.asyncio
async def test_validate_ticket_update_success():
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="UpdateMe",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, ticket)
        manager = EnhancedOperationsManager(db)
        res = await manager.validate_operation_before_execution(
            "update_ticket", ticket.Ticket_ID, {"Subject": "New"}
        )
        assert res.is_valid
        assert not res.blocking_errors


@pytest.mark.asyncio
async def test_validate_ticket_update_invalid_field():
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="Invalid",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, ticket)
        manager = EnhancedOperationsManager(db)
        res = await manager.validate_operation_before_execution(
            "update_ticket", ticket.Ticket_ID, {"BadField": "x"}
        )
        assert not res.is_valid
        assert res.blocking_errors


@pytest.mark.asyncio
async def test_validate_ticket_assignment_missing_email():
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="Assign",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID=1,
        )
        await TicketManager().create_ticket(db, ticket)
        manager = EnhancedOperationsManager(db)
        res = await manager.validate_operation_before_execution(
            "assign_ticket", ticket.Ticket_ID, {"assignee_name": "A"}
        )
        assert not res.is_valid
        assert res.blocking_errors


@pytest.mark.asyncio
async def test_validate_ticket_closure_ticket_not_found():
    async with SessionLocal() as db:
        manager = EnhancedOperationsManager(db)
        res = await manager.validate_operation_before_execution(
            "close_ticket", 9999, {"resolution": "done"}
        )
        assert not res.is_valid
        assert res.blocking_errors
