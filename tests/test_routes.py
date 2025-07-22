import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from src.core.repositories.models import Asset, Vendor, Site, TicketAttachment
from src.infrastructure.database import SessionLocal
from datetime import datetime, UTC


import pytest_asyncio


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _create_ticket(client: AsyncClient):
    payload = {
        "Subject": "API test",
        "Ticket_Body": "Checking routes",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }
    return client.post("/ticket", json=payload)


async def _add_asset(label: str = "Asset1") -> Asset:
    async with SessionLocal() as db:
        asset = Asset(Label=label)
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return asset


async def _add_vendor(name: str = "Vendor1") -> Vendor:
    async with SessionLocal() as db:
        vendor = Vendor(Name=name)
        db.add(vendor)
        await db.commit()
        await db.refresh(vendor)
        return vendor


async def _add_site(label: str = "Site1") -> Site:
    async with SessionLocal() as db:
        site = Site(Label=label)
        db.add(site)
        await db.commit()
        await db.refresh(site)
        return site


@pytest.mark.asyncio
async def test_create_and_get_ticket(client: AsyncClient):
    resp = await _create_ticket(client)
    assert resp.status_code == 201
    created = resp.json()
    tid = created["Ticket_ID"]

    list_resp = await client.get("/tickets/expanded")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["Ticket_ID"] == tid
    assert "status_label" in item
    assert data["skip"] == 0
    assert data["limit"] == 10

    get_resp = await client.get(f"/ticket/{tid}")
    assert get_resp.status_code == 200
    ticket_json = get_resp.json()
    assert ticket_json["Subject"] == "API test"
    assert "status_label" in ticket_json


@pytest.mark.asyncio
async def test_get_ticket_not_found(client: AsyncClient):
    resp = await client.get("/ticket/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_ticket(client: AsyncClient):

    resp = await _create_ticket(client)
    assert resp.status_code == 201
    ticket = resp.json()
    tid = ticket["Ticket_ID"]

    resp = await client.put(f"/ticket/{tid}", json={"Subject": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["Subject"] == "Updated"


@pytest.mark.asyncio
async def test_update_ticket_multiple_fields(client: AsyncClient):
    resp = await _create_ticket(client)
    assert resp.status_code == 201
    ticket = resp.json()
    tid = ticket["Ticket_ID"]

    payload = {"Assigned_Name": "Agent Smith", "Ticket_Status_ID": 2, "Severity_ID": 3}
    resp = await client.put(f"/ticket/{tid}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["Assigned_Name"] == "Agent Smith"
    assert data["Ticket_Status_ID"] == 2
    assert data["Severity_ID"] == 3


@pytest.mark.asyncio
async def test_update_ticket_invalid_field(client: AsyncClient):
    resp = await _create_ticket(client)
    assert resp.status_code == 201
    ticket = resp.json()
    tid = ticket["Ticket_ID"]

    resp = await client.put(f"/ticket/{tid}", json={"BadField": "x"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_asset_vendor_site_routes(client: AsyncClient):
    asset = await _add_asset()
    vendor = await _add_vendor()
    site = await _add_site()

    resp = await client.get(f"/asset/{asset.ID}")
    assert resp.status_code == 200
    assert resp.json()["Label"] == asset.Label

    resp = await client.get("/assets")
    assert resp.status_code == 200
    assert resp.json()[0]["ID"] == asset.ID

    resp = await client.get(f"/vendor/{vendor.ID}")
    assert resp.status_code == 200
    assert resp.json()["Name"] == vendor.Name

    resp = await client.get("/vendors")
    assert resp.status_code == 200
    assert resp.json()[0]["ID"] == vendor.ID

    resp = await client.get(f"/site/{site.ID}")
    assert resp.status_code == 200
    assert resp.json()["Label"] == site.Label

    resp = await client.get("/sites")
    assert resp.status_code == 200
    assert resp.json()[0]["ID"] == site.ID


@pytest_asyncio.fixture
async def ticket_attachments(client: AsyncClient):
    resp = await _create_ticket(client)
    assert resp.status_code == 201
    tid = resp.json()["Ticket_ID"]
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        att1 = TicketAttachment(
            Ticket_ID=tid,
            Name="file1.txt",
            WebURl="http://example.com/file1.txt",
            UploadDateTime=now,
        )
        att2 = TicketAttachment(
            Ticket_ID=tid,
            Name="file2.txt",
            WebURl="http://example.com/file2.txt",
            UploadDateTime=now,
        )
        db.add_all([att1, att2])
        await db.commit()
        await db.refresh(att1)
        await db.refresh(att2)
    return tid, [att1, att2]


@pytest.mark.asyncio
async def test_ticket_attachments_endpoint(
    client: AsyncClient, ticket_attachments
):
    tid, created = ticket_attachments
    resp = await client.get(f"/lookup/ticket/{tid}/attachments")
    assert resp.status_code == 200
    data = sorted(resp.json(), key=lambda d: d["ID"])
    expected = sorted(
        [
            {
                "ID": att.ID,
                "Ticket_ID": tid,
                "Name": att.Name,
                "WebURl": att.WebURl,
            }
            for att in created
        ],
        key=lambda d: d["ID"],
    )
    result = [
        {
            "ID": item["ID"],
            "Ticket_ID": item["Ticket_ID"],
            "Name": item["Name"],
            "WebURl": item["WebURl"],
        }
        for item in data
    ]
    assert result == expected
