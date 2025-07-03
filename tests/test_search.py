import os
import asyncio
import pytest
from db.models import Base, Ticket
from db.mssql import engine, SessionLocal
from datetime import datetime, UTC
from tools.ticket_tools import create_ticket, search_tickets_expanded

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")


async def _setup_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
        await conn.exec_driver_sql(
            """
            CREATE VIEW V_Ticket_Master_Expanded AS
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
        )

asyncio.get_event_loop().run_until_complete(_setup_models())


@pytest.mark.asyncio
async def test_search_tickets():
    async with SessionLocal() as db:
        t = Ticket(
            Subject="Network issue",
            Ticket_Body="Cannot connect",
            Created_Date=datetime.now(UTC),
        )

        await create_ticket(db, t)
        results = await search_tickets_expanded(db, "Network")
        assert results and results[0].Subject == "Network issue"
