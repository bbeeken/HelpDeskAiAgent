import pytest
from httpx import AsyncClient
from main import app
from db.models import Asset, Vendor, Site
from db.mssql import SessionLocal


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
    assert resp.status_code == 200
    created = resp.json()
    tid = created["Ticket_ID"]

    list_resp = await client.get("/tickets")
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
