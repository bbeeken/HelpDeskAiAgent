from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DB_CONN_STRING

engine_args = {}
if DB_CONN_STRING and DB_CONN_STRING.startswith("mssql"):
    engine_args["fast_executemany"] = True

engine = create_engine(DB_CONN_STRING or "sqlite:///:memory:", **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
