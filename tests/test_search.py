import os
from sqlalchemy.orm import Session
from db.models import Base, Ticket
from db.mssql import engine, SessionLocal
from services.ticket_service import TicketService
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
        service = TicketService(db)
        service.create_ticket(t)
        results = service.search_tickets("Network")
        assert results and results[0].Subject == "Network issue"
    finally:
        db.close()


def test_search_tickets_escape_wildcards():
    db: Session = SessionLocal()
    try:
        t = Ticket(
            Subject="Another issue",
            Ticket_Body="Body text",
            Created_Date=datetime.utcnow(),
        )
        create_ticket(db, t)
        # Raw '%' should not match everything once escaped
        assert search_tickets(db, "%") == []
        assert search_tickets(db, "_") == []
    finally:
        db.close()
