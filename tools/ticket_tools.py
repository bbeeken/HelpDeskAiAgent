from sqlalchemy.orm import Session
from db.models import Ticket

def get_ticket(db: Session, ticket_id: int):
    return db.query(Ticket).filter(Ticket.Ticket_ID == ticket_id).first()

def list_tickets(db: Session, skip: int = 0, limit: int = 10):
    return db.query(Ticket).offset(skip).limit(limit).all()

def create_ticket(db: Session, ticket_obj: Ticket):
    db.add(ticket_obj)
    db.commit()
    db.refresh(ticket_obj)
    return ticket_obj
