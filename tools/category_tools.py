from sqlalchemy.orm import Session
from db.models import TicketCategory

def list_categories(db: Session):
    return db.query(TicketCategory).all()
