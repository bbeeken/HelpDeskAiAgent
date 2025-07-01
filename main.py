from fastapi import FastAPI
from api.routes import router
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db.mssql import engine
from config import DB_CONN_STRING

app = FastAPI(title="Truck Stop MCP Helpdesk API")
app.include_router(router)


@app.on_event("startup")
def verify_database_connection():
    if not DB_CONN_STRING:
        raise RuntimeError("DB_CONN_STRING environment variable not set")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Database connection failed: {exc}")
