import os

# Pydantic 1.x fails on Python 3.12 unless this shim is disabled
os.environ.setdefault("PYDANTIC_DISABLE_STD_TYPES_SHIM", "1")

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DB_CONN_STRING", "sqlite:///:memory:")

import db.mssql as mssql
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from db.models import Base
import pytest

# Use a StaticPool so the in-memory DB is shared across threads
mssql.engine = create_engine(
    os.environ["DB_CONN_STRING"],
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
mssql.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=mssql.engine)
Base.metadata.create_all(mssql.engine)


@pytest.fixture(autouse=True)
def db_setup():
    Base.metadata.drop_all(bind=mssql.engine)
    Base.metadata.create_all(bind=mssql.engine)
    yield
    Base.metadata.drop_all(bind=mssql.engine)
