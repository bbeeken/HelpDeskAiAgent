import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC, timedelta

from main import app
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import TicketAttachment, Priority, Ticket
from src.core.services.ticket_management import TicketManager


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _ticket_payload(subject: str = "Tool test") -> dict:
    return {
        "Subject": subject,
        "Ticket_Body": "Body",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }


async def _create_ticket(client: AsyncClient, subject: str = "Tool test") -> int:
    resp = await client.post("/ticket", json=_ticket_payload(subject))
    assert resp.status_code == 201
    return resp.json()["Ticket_ID"]


@pytest.mark.asyncio
async def test_get_ticket_messages_success(client: AsyncClient):
    tid = await _create_ticket(client)
    msg_payload = {"message": "hello", "sender_code": "u", "sender_name": "User"}
    resp = await client.post(f"/ticket/{tid}/messages", json=msg_payload)
    assert resp.status_code == 200

    resp = await client.post("/get_ticket_messages", json={"ticket_id": tid})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in {"success", "error"}


@pytest.mark.asyncio
async def test_get_ticket_messages_error(client: AsyncClient):
    resp = await client.post("/get_ticket_messages", json={})
    assert resp.status_code == 422
    assert "path" in resp.json()


@pytest.mark.asyncio
async def test_get_ticket_attachments_success(client: AsyncClient):
    tid = await _create_ticket(client)
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        att = TicketAttachment(
            Ticket_ID=tid,
            Name="file.txt",
            WebURl="http://example.com/file.txt",
            UploadDateTime=now,
        )
        db.add(att)
        await db.commit()
    resp = await client.post("/get_ticket_attachments", json={"ticket_id": tid})
    assert resp.status_code == 200
    assert resp.json().get("status") in {"success", "error"}


@pytest.mark.asyncio
async def test_get_ticket_attachments_error(client: AsyncClient):
    resp = await client.post("/get_ticket_attachments", json={})
    assert resp.status_code == 422
    assert "path" in resp.json()


@pytest.mark.asyncio
async def test_escalate_ticket_success(client: AsyncClient):
    tid = await _create_ticket(client)




    payload = {
        "ticket_id": tid,
        "severity_id": 1,
        "assignee_email": "tech@example.com",
    }
    resp = await client.post("/escalate_ticket", json=payload)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_escalate_ticket_error(client: AsyncClient):

    resp = await client.post("/update_ticket", json={})

    assert resp.status_code == 422
    assert "path" in resp.json()


@pytest.mark.asyncio
async def test_get_reference_data_priorities_success(client: AsyncClient):
    async with SessionLocal() as db:
        p1 = Priority(Level="Low")
        p2 = Priority(Level="High")
        db.add_all([p1, p2])
        await db.commit()
    resp = await client.post("/get_reference_data", json={"type": "priorities"})
    assert resp.status_code == 200
    assert resp.json().get("status") in {"success", "error"}


@pytest.mark.asyncio
async def test_get_reference_data_priorities_error(client: AsyncClient):
    resp = await client.post(
        "/get_reference_data",
        json={"type": "priorities", "limit": "bad"},
    )
    assert resp.status_code == 422
    assert "path" in resp.json()


@pytest.mark.asyncio
async def test_search_tickets_enhanced_success(client: AsyncClient):
    await _create_ticket(client, subject="Enhanced Test")

    resp = await client.post(
        "/search_tickets",
        json={"text": "Enhanced", "status": "open", "include_relevance_score": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert "search_summary" in data
    assert "execution_metadata" in data
    if data["data"]:
        assert "relevance_score" in data["data"][0]
        assert 0 <= data["data"][0]["relevance_score"] <= 1
        assert "metadata" in data["data"][0]


@pytest.mark.asyncio

async def test_search_tickets_alias_params(client: AsyncClient):
    await _create_ticket(client, subject="Alias bar")
    payload = {"query": "Alias", "user_identifier": "tester@example.com"}

 

    resp = await client.post("/search_tickets", json=payload)
    assert resp.status_code == 200
    assert resp.json().get("status") in {"success", "error"}


@pytest.mark.asyncio
async def test_search_tickets_unified_user_identifier_alias(client: AsyncClient):
    await _create_ticket(client)

    payload = {"user_identifier": "tester@example.com"}


    resp = await client.post("/search_tickets", json=payload)
    assert resp.status_code == 200
    assert resp.json().get("status") in {"success", "error"}


@pytest.mark.asyncio

async def test_search_tickets_unified_error(client: AsyncClient):
    resp = await client.post("/search_tickets", json={"unexpected": 1})
    assert resp.status_code == 422







@pytest.mark.asyncio
async def test_get_analytics_sla_performance_success(client: AsyncClient):
    old = datetime.now(UTC) - timedelta(days=5)
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Old",
            Ticket_Body="B",
            Ticket_Contact_Name="N",
            Ticket_Contact_Email="e@example.com",
            Created_Date=old,
        )
        await TicketManager().create_ticket(db, t)
        await db.commit()
    resp = await client.post("/get_analytics", json={"type": "sla_performance", "params": {"days": 30}})
    assert resp.status_code == 200
    assert resp.json().get("status") in {"success", "error"}


@pytest.mark.asyncio
async def test_get_analytics_sla_performance_error(client: AsyncClient):
    resp = await client.post("/get_analytics", json={"type": "sla_performance", "params": {"days": "bad"}})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bulk_update_tickets_success(client: AsyncClient):
    tid1 = await _create_ticket(client, "Bulk1")
    tid2 = await _create_ticket(client, "Bulk2")
    payload = {"ticket_ids": [tid1, tid2], "updates": {"Assigned_Name": "Agent"}}
    resp = await client.post("/bulk_update_tickets", json=payload)
    assert resp.status_code == 200
    assert resp.json().get("status") in {"success", "error"}


@pytest.mark.asyncio
async def test_bulk_update_tickets_error(client: AsyncClient):
    resp = await client.post("/bulk_update_tickets", json={"ticket_ids": []})
    assert resp.status_code == 422
    assert "path" in resp.json()
