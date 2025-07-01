from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DB_CONN_STRING

engine_args = {}
if DB_CONN_STRING and DB_CONN_STRING.startswith("mssql"):
    engine_args["fast_executemany"] = True

engine = create_async_engine(
    DB_CONN_STRING or "sqlite+aiosqlite:///:memory:",
    **engine_args,
)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
