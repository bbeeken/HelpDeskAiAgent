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
            text("SELECT Created_Date FROM Tickets_Master WHERE Ticket_ID=:id"),
            {"id": tid},
        )
        created_raw = result.scalar_one()

    # Should be parseable without raising
    parse_db_datetime(created_raw)
