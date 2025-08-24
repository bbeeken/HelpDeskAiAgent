import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from main import app
from src.infrastructure.database import SessionLocal
from src.shared.utils.date_format import parse_db_datetime


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_ticket_stores_formatted_date(client: AsyncClient):
    payload = {
        "Subject": "Date regression",
        "Ticket_Body": "ensure date formatting",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }
    resp = await client.post("/ticket", json=payload)
    assert resp.status_code == 201
    tid = resp.json()["Ticket_ID"]

    async with SessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT Created_Date, LastModified, Closed_Date FROM Tickets_Master WHERE Ticket_ID=:id"
            ),
            {"id": tid},
        )
        created_raw, lastmod_raw, closed_raw = result.one()

    # Created_Date and LastModified should be populated and parseable
    parse_db_datetime(created_raw)
    parse_db_datetime(lastmod_raw)
    # Closed_Date should default to NULL
    assert closed_raw is None
