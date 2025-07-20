from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool
from typing import Any
from config import DB_CONN_STRING


def get_engine_args(conn_string: str) -> dict[str, Any]:
    base_args = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }

    if conn_string.startswith("mssql"):
        if conn_string.startswith("mssql+pyodbc"):
            raise RuntimeError("Use async driver 'mssql+aioodbc'")
        base_args.update({"poolclass": AsyncAdaptedQueuePool, "fast_executemany": True})
    elif conn_string.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        base_args.update({"poolclass": StaticPool, "connect_args": {"check_same_thread": False}})

    return base_args

engine = create_async_engine(
    DB_CONN_STRING or "sqlite+aiosqlite:///:memory:",
    **get_engine_args(DB_CONN_STRING or "sqlite+aiosqlite:///:memory:"),
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
