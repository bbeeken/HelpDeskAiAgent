from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from config import DB_CONN_STRING
import logging
import pyodbc


print(pyodbc.drivers())

engine_args: dict[str, object] = {}

if DB_CONN_STRING and DB_CONN_STRING.startswith("mssql"):
    from pathlib import Path

    if not Path(".env").exists():
        print("❌ .env file not found!")
        print("Create one by copying .env.example:")
        print("  cp .env.example .env")

    if DB_CONN_STRING.startswith("mssql+pyodbc"):
        logging.error("Synchronous driver detected in DB_CONN_STRING: %s", DB_CONN_STRING)
        raise RuntimeError("Use an async SQLAlchemy driver such as 'mssql+aioodbc'.")

    engine_args["fast_executemany"] = True

from pathlib import Path

engine_args = {}
if DB_CONN_STRING and DB_CONN_STRING.startswith("mssql"):
    import os

# Check if .env exists
if Path(".env").exists():
    with open(".env", "r") as f:
        content = f.read()
        if "DB_CONN_STRING" not in content:
            logging.warning("DB_CONN_STRING not found in .env")
else:
    logging.warning(".env file not found! Create one by copying .env.example")
    if DB_CONN_STRING.startswith("mssql+pyodbc"):
        logging.error("Synchronous driver detected in DB_CONN_STRING: %s", DB_CONN_STRING)
        raise RuntimeError("Use an async SQLAlchemy driver such as 'mssql+aioodbc'.")
    if DB_CONN_STRING.startswith("mssql"):
        engine_args["fast_executemany"] = True


engine = create_async_engine(
    DB_CONN_STRING or "mssql+aioodbc://${DB_USERNAME}:${DB_PASSWORD}@${DB_SERVER}/${DB_DATABASE}?driver=ODBC+Driver+18+for+SQL+Server",
    **engine_args,
)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

