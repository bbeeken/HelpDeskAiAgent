import os
from sqlalchemy.orm import Session
from db.models import Base, Ticket
from db.mssql import engine, SessionLocal
from tools.ticket_tools import search_tickets, create_ticket
from datetime import datetime

os.environ.setdefault("DB_CONN_STRING", "sqlite:///:memory:")

Base.metadata.create_all(engine)

def test_search_tickets():
    db: Session = SessionLocal()
    try:
        t = Ticket(
            Subject="Network issue",
            Ticket_Body="Cannot connect",
            Created_Date=datetime.utcnow(),
        )
        create_ticket(db, t)
        results = search_tickets(db, "Network")
        assert results and results[0].Subject == "Network issue"
    finally:
        db.close()
