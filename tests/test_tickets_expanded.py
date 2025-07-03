import pytest
from httpx import AsyncClient
import pytest_asyncio
from main import app
from db.mssql import engine

CREATE_VIEW_SQL = """
CREATE VIEW IF NOT EXISTS V_Ticket_Master_Expanded AS
SELECT tm.*, ts.Label AS Status_Label, tc.Label AS Category_Label, s.Label AS Site_Label
FROM Tickets_Master tm
LEFT JOIN Ticket_Status ts ON tm.Ticket_Status_ID = ts.ID
LEFT JOIN Ticket_Categories tc ON tm.Ticket_Category_ID = tc.ID
LEFT JOIN Sites s ON tm.Site_ID = s.ID
"""

DROP_VIEW_SQL = "DROP VIEW IF EXISTS V_Ticket_Master_Expanded"


@pytest_asyncio.fixture(autouse=True)
async def expanded_view(db_setup):
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP TABLE IF EXISTS V_Ticket_Master_Expanded")
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
    assert "Status_Label" in item
    assert "Category_Label" in item
    assert "Site_Label" in item


from schemas.ticket import TicketExpandedOut


def test_ticket_expanded_schema():
    data = {"Ticket_ID": 1, "Subject": "s", "Status_Label": "Open"}
    obj = TicketExpandedOut(**data)
    assert obj.Ticket_ID == 1
    assert obj.Status_Label == "Open"
