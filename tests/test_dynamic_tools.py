import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_dynamic_tool_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_ticket", json={"ticket_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in {"success", "error"}

        resp = await client.post("/get_ticket", json={"ticket_id": 1, "extra": 1})
        assert resp.status_code == 422

        resp = await client.post("/get_ticket", json={})
        assert resp.status_code == 422

        resp = await client.post("/get_ticket", json={"ticket_id": "one"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_dynamic_tool_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_ticket", json={"ticket_id": "bad"})
        assert resp.status_code == 422

        resp = await client.post("/get_ticket", json={})
        assert resp.status_code == 422


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
        assert "list_tickets" in names


@pytest.mark.asyncio
async def test_dynamic_create_ticket():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "Subject": "Dynamic",
            "Ticket_Body": "Created via tool",
            "Ticket_Contact_Name": "Tester",
            "Ticket_Contact_Email": "tester@example.com",
            "Ticket_Status_ID": 2,
        }
        resp = await client.post("/create_ticket", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert data["data"]["Ticket_Status_ID"] == 2
        assert data["data"]["LastModified"] is not None


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
        ]
        for name in missing:
            resp = await client.post(f"/{name}", json={})
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_new_tool_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/get_analytics", json={"type": "status_counts"})
        assert resp.status_code in {200, 404}
        if resp.status_code == 200:
            assert resp.json().get("status") in {"success", "error"}

        resp = await client.post("/list_reference_data", json={"type": "sites"})
        assert resp.status_code in {200, 404}
        if resp.status_code == 200:
            assert resp.json().get("status") in {"success", "error"}
