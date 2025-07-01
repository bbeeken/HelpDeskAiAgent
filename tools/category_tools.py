from sqlalchemy.orm import Session
from db.models import TicketCategory


def list_categories(db: Session) -> list[TicketCategory]:
    return db.query(TicketCategory).all()
