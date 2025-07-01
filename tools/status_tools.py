from sqlalchemy.orm import Session
from db.models import TicketStatus


def list_statuses(db: Session):
    return db.query(TicketStatus).all()
