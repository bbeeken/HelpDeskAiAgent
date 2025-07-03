import os

# Pydantic 1.x fails on Python 3.12 unless this shim is disabled
os.environ.setdefault("PYDANTIC_DISABLE_STD_TYPES_SHIM", "1")

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

import db.mssql as mssql
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from db.models import Base
from sqlalchemy import text
import pytest
import pytest_asyncio

# Use a StaticPool so the in-memory DB is shared across threads
mssql.engine = create_async_engine(
    os.environ["DB_CONN_STRING"],
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
mssql.SessionLocal = async_sessionmaker(bind=mssql.engine, expire_on_commit=False)

async def _init_models():
    async with mssql.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("DROP VIEW IF EXISTS V_Ticket_Master_Expanded"))
        await conn.execute(text(
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
        ))

import asyncio
asyncio.get_event_loop().run_until_complete(_init_models())


@pytest_asyncio.fixture(autouse=True)
async def db_setup():
    async with mssql.engine.begin() as conn:
        await conn.execute(text("DROP VIEW IF EXISTS V_Ticket_Master_Expanded"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
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
        ))
    yield
    async with mssql.engine.begin() as conn:
        await conn.execute(text("DROP VIEW IF EXISTS V_Ticket_Master_Expanded"))
        await conn.run_sync(Base.metadata.drop_all)
