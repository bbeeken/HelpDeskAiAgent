from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool
from config import DB_CONN_STRING
import logging


engine_args: dict[str, object] = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "poolclass": AsyncAdaptedQueuePool,
}

if DB_CONN_STRING and DB_CONN_STRING.startswith("mssql"):
    if DB_CONN_STRING.startswith("mssql+pyodbc"):
        logging.error("Synchronous driver detected in DB_CONN_STRING: %s", DB_CONN_STRING)
        raise RuntimeError("Use an async SQLAlchemy driver such as 'mssql+aioodbc'.")
    engine_args["fast_executemany"] = True

engine = create_async_engine(
    DB_CONN_STRING or "sqlite+aiosqlite:///:memory:",
    **engine_args,
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
