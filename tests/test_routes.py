import pytest
from httpx import AsyncClient
from main import app


import pytest_asyncio


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


async def _create_ticket(client: AsyncClient):
    payload = {
        "Subject": "API test",
        "Ticket_Body": "Checking routes",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }
    response = await client.post("/ticket", json=payload)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_create_and_get_ticket(client: AsyncClient):
    created = await _create_ticket(client)
    tid = created["Ticket_ID"]

    list_resp = await client.get("/tickets")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    assert data["items"][0]["Ticket_ID"] == tid
    assert data["skip"] == 0
    assert data["limit"] == 10

    get_resp = await client.get(f"/ticket/{tid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["Subject"] == "API test"


@pytest.mark.asyncio
async def test_get_ticket_not_found(client: AsyncClient):
    resp = await client.get("/ticket/999")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error_code"] == "NOT_FOUND"
