from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from db.models import Ticket

def get_ticket(db: Session, ticket_id: int):
    return db.query(Ticket).filter(Ticket.Ticket_ID == ticket_id).first()

def list_tickets(db: Session, skip: int = 0, limit: int = 10):
    return db.query(Ticket).offset(skip).limit(limit).all()

def create_ticket(db: Session, ticket_obj: Ticket):
    db.add(ticket_obj)
    try:
        db.commit()
        db.refresh(ticket_obj)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {e}")
    return ticket_obj
