from schemas.ticket import TicketExpandedOut
import pytest
from httpx import AsyncClient, ASGITransport
import pytest_asyncio
from main import app
from db.mssql import engine
from db.models import VTicketMasterExpanded
from db.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL as CREATE_VIEW_SQL

DROP_VIEW_SQL = "DROP VIEW IF EXISTS V_Ticket_Master_Expanded"


@pytest_asyncio.fixture(autouse=True)
async def expanded_view(db_setup):
    async with engine.begin() as conn:

        await conn.exec_driver_sql(DROP_VIEW_SQL)
        await conn.exec_driver_sql("DROP TABLE IF EXISTS V_Ticket_Master_Expanded")
        await conn.exec_driver_sql(CREATE_VIEW_SQL)
    yield
    async with engine.begin() as conn:
        await conn.exec_driver_sql(DROP_VIEW_SQL)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_tickets_expanded_endpoint(client: AsyncClient):
    payload = {
        "Subject": "Exp",
        "Ticket_Body": "Body",
        "Ticket_Contact_Name": "T",
        "Ticket_Contact_Email": "t@example.com",
    }
    created = await client.post("/ticket", json=payload)
    assert created.status_code == 201
    tid = created.json()["Ticket_ID"]

    resp = await client.get("/tickets/expanded")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["Ticket_ID"] == tid
    assert "Ticket_Status_Label" in item
    assert "Ticket_Category_Label" in item
    assert "Site_Label" in item
    assert "Site_ID" in item
    assert "Closed_Date" in item
    assert item["Closed_Date"] is None
    assert "LastModified" in item
    assert item["LastModified"] is None


def test_ticket_expanded_schema():
    data = {
        "Ticket_ID": 1,
        "Subject": "s",
        "Ticket_Status_Label": "Open",
        "Site_ID": 1,
    }
    obj = TicketExpandedOut(**data)
    assert obj.Ticket_ID == 1
    assert obj.status_label == "Open"
    assert obj.Closed_Date is None
    assert obj.LastModified is None


@pytest.mark.asyncio
async def test_ticket_filtering(client: AsyncClient):
    await client.post(
        "/ticket",
        json={
            "Subject": "Foo",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "n",
            "Ticket_Contact_Email": "e@example.com",
        },
    )
    await client.post(
        "/ticket",
        json={
            "Subject": "Bar",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "n",
            "Ticket_Contact_Email": "e@example.com",
        },
    )

    resp = await client.get("/tickets/expanded", params={"Subject": "Foo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["Subject"] == "Foo"


@pytest.mark.asyncio
async def test_ticket_sorting(client: AsyncClient):
    await client.post(
        "/ticket",
        json={
            "Subject": "First",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "n",
            "Ticket_Contact_Email": "e@example.com",
        },
    )
    second = await client.post(
        "/ticket",
        json={
            "Subject": "Second",
            "Ticket_Body": "b",
            "Ticket_Contact_Name": "n",
            "Ticket_Contact_Email": "e@example.com",
        },
    )

    resp = await client.get("/tickets/expanded", params={"sort": "-Ticket_ID"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["Ticket_ID"] == second.json()["Ticket_ID"]


def test_ticket_expanded_from_orm_blank_assigned_email():
    ticket = VTicketMasterExpanded(
        Ticket_ID=1,
        Subject="s",
        Ticket_Body="b",
        Ticket_Contact_Name="n",
        Ticket_Contact_Email="c@example.com",
        Assigned_Email="",
    )
    obj = TicketExpandedOut.model_validate(ticket)
    assert obj.Assigned_Email is None
    assert obj.Closed_Date is None
    assert obj.LastModified is None
