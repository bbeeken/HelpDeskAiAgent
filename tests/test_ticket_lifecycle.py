import pytest
import pytest_asyncio
import httpx
from fastapi import HTTPException
from main import app


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


async def create_sample_ticket(client: httpx.AsyncClient):
    payload = {
        "Subject": "Lifecycle",
        "Ticket_Body": "Testing lifecycle",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }
    response = await client.post("/ticket", json=payload)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_ticket_full_lifecycle(client: httpx.AsyncClient):
    ticket = await create_sample_ticket(client)
    tid = ticket["Ticket_ID"]

    update_resp = await client.put(
        f"/ticket/{tid}", json={"Assigned_Name": "Agent", "Ticket_Status_ID": 2}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["Assigned_Name"] == "Agent"

    msg_payload = {"message": "hello", "sender_code": "u1", "sender_name": "User"}
    msg_resp = await client.post(f"/ticket/{tid}/messages", json=msg_payload)
    assert msg_resp.status_code == 200
    assert msg_resp.json()["Message"] == "hello"

    msgs = await client.get(f"/ticket/{tid}/messages")
    assert msgs.status_code == 200
    assert msgs.json()[0]["Message"] == "hello"

    close_resp = await client.put(f"/ticket/{tid}", json={"Ticket_Status_ID": 3})
    assert close_resp.status_code == 200
    assert close_resp.json()["Ticket_Status_ID"] == 3

    delete_resp = await client.delete(f"/ticket/{tid}")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"deleted": True}


@pytest.mark.asyncio
async def test_update_ticket_not_found(client: httpx.AsyncClient):
    resp = await client.put("/ticket/99999", json={"Subject": "none"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_ticket_not_found(client: httpx.AsyncClient):
    resp = await client.delete("/ticket/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_ticket_validation_error(client: httpx.AsyncClient):
    bad_payload = {
        "Subject": "Bad",
        "Ticket_Body": "Bad",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "not-an-email",
    }
    resp = await client.post("/ticket", json=bad_payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_ticket_db_failure(client: httpx.AsyncClient, monkeypatch):
    def fail_create(db, obj):
        raise HTTPException(status_code=500, detail="fail")

    monkeypatch.setattr("api.routes.create_ticket", fail_create)
    payload = {
        "Subject": "DB fail",
        "Ticket_Body": "body",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }
    resp = await client.post("/ticket", json=payload)
    assert resp.status_code == 500
