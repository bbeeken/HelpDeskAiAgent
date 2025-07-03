import pytest
from httpx import AsyncClient
import pytest_asyncio
from main import app
from db.mssql import engine

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
       t.Severity_ID,
       t.Assigned_Vendor_ID,
       v.Name AS Assigned_Vendor_Name,
       t.Resolution
FROM Tickets_Master t
LEFT JOIN Ticket_Status ts ON ts.ID = t.Ticket_Status_ID
LEFT JOIN Assets a ON a.ID = t.Asset_ID
LEFT JOIN Sites s ON s.ID = t.Site_ID
LEFT JOIN Ticket_Categories c ON c.ID = t.Ticket_Category_ID
LEFT JOIN Vendors v ON v.ID = t.Assigned_Vendor_ID
"""

DROP_VIEW_SQL = "DROP VIEW IF EXISTS V_Ticket_Master_Expanded"


@pytest_asyncio.fixture(autouse=True)
async def expanded_view(db_setup):
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
        await conn.exec_driver_sql(DROP_VIEW_SQL)
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
    assert "Ticket_Status_Label" in item
    assert "Ticket_Category_Label" in item
    assert "Site_Label" in item


from schemas.ticket import TicketExpandedOut


def test_ticket_expanded_schema():
    data = {"Ticket_ID": 1, "Subject": "s", "Ticket_Status_Label": "Open"}
    obj = TicketExpandedOut(**data)
    assert obj.Ticket_ID == 1
    assert obj.Ticket_Status_Label == "Open"
