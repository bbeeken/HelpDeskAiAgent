import pytest
from httpx import AsyncClient
from main import app


import pytest_asyncio


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


def _create_ticket(client: AsyncClient):
    payload = {
        "Subject": "API test",
        "Ticket_Body": "Checking routes",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }
    return client.post("/ticket", json=payload)


@pytest.mark.asyncio
async def test_create_and_get_ticket(client: AsyncClient):
    resp = await _create_ticket(client)
    assert resp.status_code == 200
    created = resp.json()
    tid = created["Ticket_ID"]

    list_resp = await client.get("/tickets")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["Ticket_ID"] == tid
    assert "Ticket_Status_Label" in item
    assert data["skip"] == 0
    assert data["limit"] == 10

    get_resp = await client.get(f"/ticket/{tid}")
    assert get_resp.status_code == 200
    ticket_json = get_resp.json()
    assert ticket_json["Subject"] == "API test"
    assert "Ticket_Status_Label" in ticket_json


@pytest.mark.asyncio
async def test_get_ticket_not_found(client: AsyncClient):
    resp = await client.get("/ticket/999")
    assert resp.status_code == 404



@pytest.mark.asyncio
async def test_update_ticket(client: AsyncClient):

    resp = await _create_ticket(client)
    assert resp.status_code == 200
    ticket = resp.json()
    tid = ticket["Ticket_ID"]


    resp = await client.put(f"/ticket/{tid}", json={"Subject": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["Subject"] == "Updated"




@pytest.mark.asyncio
async def test_update_ticket_invalid_field(client: AsyncClient):
    resp = await _create_ticket(client)
    assert resp.status_code == 200
    ticket = resp.json()
    tid = ticket["Ticket_ID"]


    resp = await client.put(f"/ticket/{tid}", json={"BadField": "x"})
    assert resp.status_code == 422

