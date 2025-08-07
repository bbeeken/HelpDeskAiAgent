import pytest
import pytest_asyncio
import base64
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC, timedelta

from sqlalchemy import select, text


from main import app
from tests.conftest import app_lifespan  # noqa: F401
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import (
    TicketAttachment,
    Priority,
    Ticket,
    TicketMessage,
)
from src.core.services.ticket_management import TicketManager

from src.shared.utils.date_format import format_db_datetime, parse_db_datetime



@pytest_asyncio.fixture
async def client(app_lifespan):  # rely on autouse lifespan setup
    transport = ASGITransport(app=app, lifespan="on")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _ticket_payload(subject: str = "Tool test") -> dict:
    return {
        "Subject": subject,
        "Ticket_Body": "Body",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
        "Created_Date": format_db_datetime(datetime.now(UTC)),
    }


async def _create_ticket(client: AsyncClient, subject: str = "Tool test") -> int:
    resp = await client.post("/ticket", json=_ticket_payload(subject))
    assert resp.status_code == 201
    return resp.json()["Ticket_ID"]


@pytest.mark.asyncio
async def test_create_ticket_ms_precision(client: AsyncClient):
    tid = await _create_ticket(client)
    async with SessionLocal() as session:
        result = await session.execute(
            text("SELECT Created_Date FROM Tickets_Master WHERE Ticket_ID=:id"),
            {"id": tid},
        )
        created_raw = result.scalar_one()
    # Ensure string is parseable and has millisecond precision
    parse_db_datetime(created_raw)
    assert len(created_raw.split(".")[1]) == 3


@pytest.mark.asyncio
async def test_get_ticket_messages_success(client: AsyncClient):
    tid = await _create_ticket(client)
    msg_payload = {"message": "hello", "sender_code": "u", "sender_name": "User"}
    resp = await client.post(f"/ticket/{tid}/messages", json=msg_payload)
    assert resp.status_code == 200

    resp = await client.post("/get_ticket_messages", json={"ticket_id": tid})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("ticket_id") == tid
    assert data.get("count") == 1
    assert data.get("data")
    assert data["data"][0]["Message"] == "hello"


@pytest.mark.asyncio
async def test_get_ticket_messages_error(client: AsyncClient):
    resp = await client.post("/get_ticket_messages", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "path" in data
    assert "payload" in data


@pytest.mark.asyncio
async def test_ticket_message_stores_millisecond_precision(client: AsyncClient):
    """Messages should persist creation dates only to millisecond precision."""
    tid = await _create_ticket(client)
    payload = {"message": "hi", "sender_code": "u", "sender_name": "User"}
    resp = await client.post(f"/ticket/{tid}/messages", json=payload)
    assert resp.status_code == 200

    async with SessionLocal() as db:
        msg_result = await db.execute(
            select(TicketMessage).filter(TicketMessage.Ticket_ID == tid)
        )
        msg = msg_result.scalars().first()
        assert msg is not None
        assert msg.DateTimeStamp.tzinfo is not None
        assert msg.DateTimeStamp.microsecond % 1000 == 0

        ticket_result = await db.execute(
            select(Ticket.Created_Date).filter(Ticket.Ticket_ID == tid)
        )
        created = ticket_result.scalar_one()
        assert created.tzinfo is not None
        assert created.microsecond % 1000 == 0


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
            FileContent="content",
            Binary=False,
            ContentBytes=None,
        )
        db.add(att)
        await db.commit()
    resp = await client.post("/get_ticket_attachments", json={"ticket_id": tid})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("ticket_id") == tid
    assert data.get("count") == 1
    assert data.get("data")
    att = data["data"][0]
    assert att["Name"] == "file.txt"
    assert att["WebURL"] == "http://example.com/file.txt"
    assert att["FileContent"] == "content"
    assert att["Binary"] is False
    assert att["ContentBytes"] is None


@pytest.mark.asyncio
async def test_get_ticket_attachments_error(client: AsyncClient):
    resp = await client.post("/get_ticket_attachments", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "path" in data
    assert "payload" in data


@pytest.mark.asyncio
async def test_ticket_attachment_stores_millisecond_precision(
    client: AsyncClient,
):
    """Attachments should persist upload dates only to millisecond precision."""
    tid = await _create_ticket(client)
    aware = datetime(2024, 1, 1, 12, 0, 0, 654321, tzinfo=UTC)

    async with SessionLocal() as db:
        att = TicketAttachment(
            Ticket_ID=tid,
            Name="precise.txt",
            WebURl="http://example.com/precise.txt",
            UploadDateTime=aware,
            FileContent="precise",
            Binary=True,
            ContentBytes=b"precise-bytes",
        )
        db.add(att)
        await db.commit()
        await db.refresh(att)

        assert att.UploadDateTime.tzinfo is not None
        assert att.UploadDateTime.microsecond % 1000 == 0

        ticket_result = await db.execute(
            select(Ticket.Created_Date).filter(Ticket.Ticket_ID == tid)
        )
        created = ticket_result.scalar_one()
        assert created.tzinfo is not None
        assert created.microsecond % 1000 == 0

    resp = await client.post("/get_ticket_attachments", json={"ticket_id": tid})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("count") == 1
    uploaded = data["data"][0]["UploadDateTime"]
    parsed = datetime.fromisoformat(uploaded)
    assert parsed.microsecond % 1000 == 0
    returned = data["data"][0]
    assert returned["FileContent"] == "precise"
    assert returned["Binary"] is True
    assert base64.b64decode(returned["ContentBytes"]) == b"precise-bytes"


@pytest.mark.asyncio
async def test_escalate_ticket_not_found(client: AsyncClient):
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
    data = resp.json()
    assert "path" in data
    assert "payload" in data


@pytest.mark.asyncio
async def test_get_reference_data_priorities_success(client: AsyncClient):
    async with SessionLocal() as db:
        p1 = Priority(Label="Low")
        p2 = Priority(Label="High")
        db.add_all([p1, p2])
        await db.commit()
    resp = await client.post("/get_reference_data", json={"type": "priorities"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("type") == "priorities"
    assert data.get("count") == 2
    levels = {item["level"] for item in data.get("data", [])}
    assert {"Low", "High"}.issubset(levels)


@pytest.mark.asyncio
async def test_get_reference_data_priorities_error(client: AsyncClient):
    resp = await client.post(
        "/get_reference_data",
        json={"type": "priorities", "limit": "bad"},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "path" in data
    assert "payload" in data


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
    data = resp.json()
    assert data.get("status") == "success"
    assert any(itm.get("Subject") == "Alias bar" for itm in data.get("data", []))
    summary_types = set(data["search_summary"]["query_type"])
    assert {"text_search", "user_filter"}.issubset(summary_types)
    assert data["execution_metadata"]["text_query"] == "Alias"
    assert data["execution_metadata"]["user_filter"] == "tester@example.com"


@pytest.mark.asyncio
async def test_search_tickets_unified_user_identifier_alias(client: AsyncClient):
    await _create_ticket(client)

    payload = {"user_identifier": "tester@example.com"}

    resp = await client.post("/search_tickets", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("count") == len(data.get("data", []))
    assert data["execution_metadata"]["user_filter"] == "tester@example.com"
    assert "user_filter" in data["search_summary"]["query_type"]


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
    resp = await client.post(
        "/get_analytics",
        json={"type": "sla_performance", "params": {"days": 30}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("time_range_days") == 30
    assert isinstance(data.get("data"), dict)
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_get_analytics_sla_performance_error(client: AsyncClient):
    resp = await client.post(
        "/get_analytics",
        json={"type": "sla_performance", "params": {"days": "bad"}},
    )
    data = resp.json()
    assert resp.status_code == 422 or data.get("status") == "error"
    if data.get("status") == "error":
        assert "error" in data


@pytest.mark.asyncio
async def test_bulk_update_tickets_success(client: AsyncClient):
    tid1 = await _create_ticket(client, "Bulk1")
    tid2 = await _create_ticket(client, "Bulk2")
    payload = {
        "ticket_ids": [tid1, tid2],
        "updates": {"Assigned_Name": "Agent"},
    }
    resp = await client.post("/bulk_update_tickets", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("total_processed") == 2
    assert data.get("total_updated") == 2
    assert data.get("total_failed") == 0
    assert len(data.get("updated", [])) == 2
    assert all(t["Assigned_Name"] == "Agent" for t in data["updated"])


@pytest.mark.asyncio
async def test_bulk_update_tickets_error(client: AsyncClient):
    resp = await client.post("/bulk_update_tickets", json={"ticket_ids": []})
    assert resp.status_code == 422
    data = resp.json()
    assert "path" in data
    assert "payload" in data


@pytest.mark.asyncio
async def test_update_ticket_open_status_error(client: AsyncClient):
    tid = await _create_ticket(client, "Ambiguous")
    payload = {"ticket_id": tid, "updates": {"status": "open"}}
    resp = await client.post("/update_ticket", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    err = data["error"]
    if isinstance(err, dict):
        err = err.get("message", "")
    err = err.lower()
    assert "ambiguous" in err
    assert "open" in err
    assert "valid options" in err
