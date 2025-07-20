from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool
from typing import Any
from config import DB_CONN_STRING


def get_engine_args(conn_string: str) -> dict[str, Any]:
    """Return engine keyword arguments based on the connection string."""
    if conn_string.startswith("sqlite"):
        # SQLite requires a special pool configuration and does not support
        # traditional connection pooling arguments such as ``pool_size`` or
        # ``max_overflow``.
        from sqlalchemy.pool import StaticPool

        return {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}

    # Arguments common to all other database types
    base_args = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    if not conn_string.startswith("sqlite"):
        base_args.update({"pool_size": 10, "max_overflow": 20})

    if conn_string.startswith("mssql"):
        if conn_string.startswith("mssql+pyodbc"):
            raise RuntimeError("Use async driver 'mssql+aioodbc'")
        base_args.update({"poolclass": AsyncAdaptedQueuePool, "fast_executemany": True})

    return base_args

engine = create_async_engine(
    DB_CONN_STRING or "sqlite+aiosqlite:///:memory:",
    **get_engine_args(DB_CONN_STRING or "sqlite+aiosqlite:///:memory:"),
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
