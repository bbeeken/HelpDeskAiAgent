from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from db.models import Ticket


class TicketService:
    """Service class providing ticket-related database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_ticket(self, ticket_id: int):
        return self.db.query(Ticket).filter(Ticket.Ticket_ID == ticket_id).first()

    def list_tickets(self, skip: int = 0, limit: int = 10):
        return self.db.query(Ticket).offset(skip).limit(limit).all()

    def create_ticket(self, ticket_obj: Ticket):
        self.db.add(ticket_obj)
        try:
            self.db.commit()
            self.db.refresh(ticket_obj)
        except SQLAlchemyError as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create ticket: {e}")
        return ticket_obj

    def update_ticket(self, ticket_id: int, updates: dict):
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        for key, value in updates.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        try:
            self.db.commit()
            self.db.refresh(ticket)
            return ticket
        except Exception:
            self.db.rollback()
            raise

    def delete_ticket(self, ticket_id: int) -> bool:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return False
        try:
            self.db.delete(ticket)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def search_tickets(self, query: str, limit: int = 10):
        like = f"%{query}%"
        return (
            self.db.query(Ticket)
            .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
            .limit(limit)
            .all()
        )
