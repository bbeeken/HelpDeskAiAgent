import os

os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

from asgi_lifespan import LifespanManager
from main import app
import asyncio
import pytest
import pytest_asyncio
from src.core.repositories.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL
from sqlalchemy import text
from src.core.repositories.models import Base, Priority
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import src.infrastructure.database as mssql
import src.core.services.analytics_reporting as analytics_reporting


# Pydantic 1.x fails on Python 3.12 unless this shim is disabled
os.environ.setdefault("PYDANTIC_DISABLE_STD_TYPES_SHIM", "1")


# Use a StaticPool so the in-memory DB is shared across threads

mssql.engine = create_async_engine(
    os.environ["DB_CONN_STRING"],
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
mssql.SessionLocal = async_sessionmaker(bind=mssql.engine, expire_on_commit=False)

# Ensure the FastAPI app and dependencies use the test engine/session
import src.api.v1.deps as deps
deps.SessionLocal = mssql.SessionLocal
import main as main_mod
main_mod.engine = mssql.engine


async def _init_models():
    async with mssql.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.get_event_loop().run_until_complete(_init_models())


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


@pytest.fixture(autouse=True)
def clear_analytics_cache():
    analytics_reporting._analytics_cache.clear()
    yield


@pytest_asyncio.fixture
async def sample_priorities():
    async with mssql.SessionLocal() as db:
        low = Priority(Level="Low")
        high = Priority(Level="High")
        db.add_all([low, high])
        await db.commit()
        await db.refresh(low)
        await db.refresh(high)
        return [low, high]
