import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_dynamic_tool_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "Subject": "Seed",
            "Ticket_Body": "Init ticket",
            "Ticket_Contact_Name": "Seeder",
            "Ticket_Contact_Email": "seed@example.com",
        }
        created = await client.post("/create_ticket", json=payload)
        assert created.status_code == 200
        created_data = created.json()
        assert created_data.get("status") == "success"
        ticket_id = created_data["data"]["Ticket_ID"]

        resp = await client.post("/get_ticket", json={"ticket_id": ticket_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        ticket = data.get("data", {})
        assert ticket.get("Ticket_ID") == ticket_id
        assert "Subject" in ticket

        resp = await client.post("/get_ticket", json={"ticket_id": ticket_id, "extra": 1})
        assert resp.status_code == 422

        resp = await client.post(
            "/get_ticket",
            json={"ticket_id": ticket_id, "include_full_context": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert data["data"]["Ticket_ID"] == ticket_id
        assert isinstance(data.get("messages"), list)
        assert isinstance(data.get("attachments"), list)
        assert "user_history" in data

        resp = await client.post("/get_ticket", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert "path" in data
        assert "payload" in data

        resp = await client.post("/get_ticket", json={"ticket_id": "one"})
        assert resp.status_code == 422
        data = resp.json()
        assert "path" in data
        assert "payload" in data


@pytest.mark.asyncio
async def test_dynamic_tool_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_ticket", json={"ticket_id": "bad"})
        assert resp.status_code == 422
        data = resp.json()
        assert "path" in data
        assert "payload" in data

        resp = await client.post("/get_ticket", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert "path" in data
        assert "payload" in data


@pytest.mark.asyncio
async def test_tools_list_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools")
        assert resp.status_code == 200
        data = resp.json()
        tools = data["tools"] if isinstance(data, dict) else data
        names = {t["name"] for t in tools}
        assert "get_ticket" in names
        assert "search_tickets" in names


@pytest.mark.asyncio
async def test_dynamic_create_ticket():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "Subject": "Dynamic",
            "Ticket_Body": "Created via tool",
            "Ticket_Contact_Name": "Tester",
            "Ticket_Contact_Email": "tester@example.com",
            "Ticket_Status_ID": "2",
        }
        resp = await client.post("/create_ticket", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert data["data"]["Ticket_Status_ID"] == "2"
        assert data["data"]["LastModified"] is not None
        assert data["data"]["LastModfiedBy"] == "Gil AI"


@pytest.mark.asyncio
async def test_removed_tools_return_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = [
            "open_by_site",
            "open_by_assigned_user",
            "tickets_by_status",
            "ticket_trend",
            "waiting_on_user",
            "sla_breaches",
            "staff_report",
            "tickets_by_timeframe",
            "list_sites",
            "list_assets",
            "list_vendors",
            "list_categories",
            "by_user",
            "get_sla_metrics",
        ]
        for name in missing:
            resp = await client.post(f"/{name}", json={})
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_new_tool_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_analytics", json={"type": "overview"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        snapshot = data.get("data", {})
        assert "ticket_counts_by_status" in snapshot
        assert "system_health" in snapshot
        assert "timestamp" in data

        resp = await client.post("/get_reference_data", json={"type": "sites"})
        assert resp.status_code == 200
        ref_data = resp.json()
        assert ref_data.get("status") == "success"
        assert ref_data.get("type") == "sites"
        assert isinstance(ref_data.get("data"), list)
        assert "count" in ref_data
        assert "total_count" in ref_data
