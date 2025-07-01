from sqlalchemy.orm import sessionmaker
from db.mssql import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
