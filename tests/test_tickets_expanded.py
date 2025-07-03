import pytest
from httpx import AsyncClient
import pytest_asyncio
from main import app
from db.mssql import engine
from db.models import VTicketMasterExpanded

CREATE_VIEW_SQL = """
CREATE VIEW IF NOT EXISTS V_Ticket_Master_Expanded AS
SELECT t.Ticket_ID,
       t.Subject,
       t.Ticket_Body,
       t.Ticket_Status_ID,
       ts.Label AS Ticket_Status_Label,
       t.Ticket_Contact_Name,
       t.Ticket_Contact_Email,
       t.Asset_ID,
       a.Label AS Asset_Label,
       t.Site_ID,
       s.Label AS Site_Label,
       t.Ticket_Category_ID,
       c.Label AS Ticket_Category_Label,
       t.Created_Date,
       t.Assigned_Name,
       t.Assigned_Email,
       t.Priority_ID,
       t.Assigned_Vendor_ID,
       v.Name AS Assigned_Vendor_Name,
       t.Resolution,
       p.Level AS Priority_Level
FROM Tickets_Master t
LEFT JOIN Ticket_Status ts ON ts.ID = t.Ticket_Status_ID
LEFT JOIN Assets a ON a.ID = t.Asset_ID
LEFT JOIN Sites s ON s.ID = t.Site_ID
LEFT JOIN Ticket_Categories c ON c.ID = t.Ticket_Category_ID
LEFT JOIN Vendors v ON v.ID = t.Assigned_Vendor_ID
LEFT JOIN Priorities p ON p.ID = t.Priority_ID
"""

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
    async with AsyncClient(app=app, base_url="http://test") as ac:
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
    assert created.status_code == 200
    tid = created.json()["Ticket_ID"]

    resp = await client.get("/tickets/expanded")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["Ticket_ID"] == tid
    assert "status_label" in item
    assert "category_label" in item
    assert "Site_Label" in item
    assert "Site_ID" in item


from schemas.ticket import TicketExpandedOut


def test_ticket_expanded_schema():
    data = {"Ticket_ID": 1, "Subject": "s", "Ticket_Status_Label": "Open", "Site_ID": 1}
    obj = TicketExpandedOut(**data)
    assert obj.Ticket_ID == 1
    assert obj.status_label == "Open"


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

    resp = await client.get("/tickets", params={"Subject": "Foo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["Subject"] == "Foo"


@pytest.mark.asyncio
async def test_ticket_sorting(client: AsyncClient):
    first = await client.post(
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
    obj = TicketExpandedOut.from_orm(ticket)
    assert obj.Assigned_Email is None
