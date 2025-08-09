import pytest
import pytest_asyncio
from datetime import datetime, UTC
from httpx import AsyncClient, ASGITransport


from main import app
from src.core.services.ticket_management import TicketManager
from src.core.repositories.models import Ticket
from src.infrastructure.database import SessionLocal


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_version_increments_on_update():
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="Version1",
            Ticket_Body="body",
            Ticket_Contact_Name="User",
            Ticket_Contact_Email="user@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID="1",
        )
        result = await TicketManager().create_ticket(db, ticket)
        await db.commit()
        tid = result.data.Ticket_ID
        orig_version = getattr(result.data, "Version", None)
        await TicketManager().update_ticket(db, tid, {"Subject": "Updated"})
        await db.commit()
        updated = await TicketManager().get_ticket(db, tid)
        assert getattr(updated, "Version", None) == (orig_version or 0) + 1


@pytest.mark.asyncio
async def test_version_unchanged_when_no_real_update():
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="NoChange",
            Ticket_Body="body",
            Ticket_Contact_Name="User",
            Ticket_Contact_Email="user@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID="1",
        )
        result = await TicketManager().create_ticket(db, ticket)
        await db.commit()
        tid = result.data.Ticket_ID
        orig_version = getattr(result.data, "Version", None)
        # Apply update with the same subject
        await TicketManager().update_ticket(db, tid, {"Subject": ticket.Subject})
        await db.commit()
        unchanged = await TicketManager().get_ticket(db, tid)
        assert getattr(unchanged, "Version", None) == orig_version


@pytest.mark.asyncio
async def test_assigned_name_not_email_after_mcp_update(client: AsyncClient):
    async with SessionLocal() as db:
        ticket = Ticket(
            Subject="MCPVersion",
            Ticket_Body="body",
            Ticket_Contact_Name="User",
            Ticket_Contact_Email="user@example.com",
            Created_Date=datetime.now(UTC),
            Ticket_Status_ID="1",
        )
        await TicketManager().create_ticket(db, ticket)
        await db.commit()
        tid = ticket.Ticket_ID

    payload = {"ticket_id": tid, "updates": {"assignee_email": "tech@example.com"}}
    resp = await client.post("/update_ticket", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data["data"].get("Assigned_Name") != "tech@example.com"
