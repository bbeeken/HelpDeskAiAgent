from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from config import DB_CONN_STRING
import logging

    if DB_CONN_STRING.startswith("mssql+pyodbc"):
        logging.error("Synchronous driver detected in DB_CONN_STRING: %s", DB_CONN_STRING)
        raise RuntimeError("Use an async SQLAlchemy driver such as 'mssql+aioodbc'.")
    if DB_CONN_STRING.startswith("mssql"):
        engine_args["fast_executemany"] = True

engine = create_async_engine(
    DB_CONN_STRING or "sqlite+aiosqlite:///:memory:",
    **engine_args,
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

