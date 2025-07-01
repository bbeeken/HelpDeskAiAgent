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



def update_ticket(db: Session, ticket_id: int, updates: dict) -> Ticket | None:
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        return None
    for key, value in updates.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)
    try:
        db.commit()
        db.refresh(ticket)
        return ticket
    except Exception:
        db.rollback()
        raise

def delete_ticket(db: Session, ticket_id: int) -> bool:
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        return False
    try:
        db.delete(ticket)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise

def search_tickets(db: Session, query: str, limit: int = 10):
    like = f"%{query}%"
    return (
        db.query(Ticket)
        .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
        .limit(limit)
        .all()
    )

