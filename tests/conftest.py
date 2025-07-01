import os

# Pydantic 1.x fails on Python 3.12 unless this shim is disabled
os.environ.setdefault("PYDANTIC_DISABLE_STD_TYPES_SHIM", "1")

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

import db.mssql as mssql
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from db.models import Base
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

import asyncio
asyncio.get_event_loop().run_until_complete(_init_models())


@pytest_asyncio.fixture(autouse=True)
async def db_setup():
    async with mssql.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with mssql.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
