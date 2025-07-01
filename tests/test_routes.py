from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _create_ticket():
    payload = {
        "Subject": "API test",
        "Ticket_Body": "Checking routes",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }
    response = client.post("/ticket", json=payload)
    assert response.status_code == 200
    return response.json()


def test_create_and_get_ticket():
    created = _create_ticket()
    tid = created["Ticket_ID"]

    list_resp = client.get("/tickets")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    assert data["items"][0]["Ticket_ID"] == tid
    assert data["skip"] == 0
    assert data["limit"] == 10

    get_resp = client.get(f"/ticket/{tid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["Subject"] == "API test"


def test_get_ticket_not_found():
    resp = client.get("/ticket/999")
    assert resp.status_code == 404
