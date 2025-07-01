from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DB_CONN_STRING

engine = create_engine(DB_CONN_STRING, fast_executemany=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
