"""Legacy wrappers around :class:`TicketService` methods."""

from sqlalchemy.orm import Session
from db.models import Ticket
from services.ticket_service import TicketService


def get_ticket(db: Session, ticket_id: int):
    """Return a single ticket using :class:`TicketService`."""
    return TicketService(db).get_ticket(ticket_id)


def list_tickets(db: Session, skip: int = 0, limit: int = 10):
    return TicketService(db).list_tickets(skip, limit)


def create_ticket(db: Session, ticket_obj: Ticket):
    return TicketService(db).create_ticket(ticket_obj)


def update_ticket(db: Session, ticket_id: int, updates: dict) -> Ticket | None:
    return TicketService(db).update_ticket(ticket_id, updates)


def delete_ticket(db: Session, ticket_id: int) -> bool:
    return TicketService(db).delete_ticket(ticket_id)


def search_tickets(db: Session, query: str, limit: int = 10):
    return TicketService(db).search_tickets(query, limit)
