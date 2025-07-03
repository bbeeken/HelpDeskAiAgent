from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DB_CONN_STRING
import logging
import pyodbc
print(pyodbc.drivers())
engine_args = {}
if DB_CONN_STRING and DB_CONN_STRING.startswith("mssql"):import os
from pathlib import Path

# Check if .env exists
if Path(".env").exists():
    print("✓ .env file exists -"+ DB_CONN_STRING)
    
    # Check content
    with open(".env", "r") as f:
        content = f.read()
        if "DB_CONN_STRING" in content:
            print("✓ DB_CONN_STRING found in .env")
        else:
            print("❌ DB_CONN_STRING not found in .env")
else:
    print("❌ .env file not found!")
    print("Create one by copying .env.example:")
    print("  cp .env.example .env")
    if DB_CONN_STRING.startswith("mssql+pyodbc"):
        logging.error("Synchronous driver detected in DB_CONN_STRING: %s", DB_CONN_STRING)
        raise RuntimeError("Use an async SQLAlchemy driver such as 'mssql+aioodbc'.")
    engine_args["fast_executemany"] = True


engine = create_async_engine(
    DB_CONN_STRING or "mssql+aioodbc://${DB_USERNAME}:${DB_PASSWORD}@${DB_SERVER}/${DB_DATABASE}?driver=ODBC+Driver+18+for+SQL+Server",
    **engine_args,
)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

