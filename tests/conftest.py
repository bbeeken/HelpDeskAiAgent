import os

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

from asgi_lifespan import LifespanManager
from main import app
import asyncio
import pytest_asyncio
from src.core.repositories.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL
from sqlalchemy import text
from src.core.repositories.models import Base
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import src.infrastructure.database as mssql

# Pydantic 1.x fails on Python 3.12 unless this shim is disabled
os.environ.setdefault("PYDANTIC_DISABLE_STD_TYPES_SHIM", "1")


# Use a StaticPool so the in-memory DB is shared across threads
# The default engine already uses StaticPool when DB_CONN_STRING points to
# SQLite, so no reconfiguration is required.


@pytest_asyncio.fixture(autouse=True)
async def app_lifespan():
    async with LifespanManager(app):
        yield


@pytest_asyncio.fixture(autouse=True)
async def db_setup():
    async with mssql.engine.begin() as conn:
        await conn.execute(text("DROP VIEW IF EXISTS V_Ticket_Master_Expanded"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL))
    yield
    async with mssql.engine.begin() as conn:
        await conn.execute(text("DROP VIEW IF EXISTS V_Ticket_Master_Expanded"))
        await conn.run_sync(Base.metadata.drop_all)
