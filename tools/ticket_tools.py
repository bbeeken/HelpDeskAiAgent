
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException

from pydantic import BaseModel

from db.models import Ticket
from services.ticket_service import TicketService



async def get_ticket(db: AsyncSession, ticket_id: int):
    return await db.get(Ticket, ticket_id)

logger = logging.getLogger(__name__)


def get_ticket(db: Session, ticket_id: int) -> Ticket | None:
    return db.query(Ticket).filter(Ticket.Ticket_ID == ticket_id).first()


def list_tickets(db: Session, skip: int = 0, limit: int = 10) -> list[Ticket]:
    return db.query(Ticket).offset(skip).limit(limit).all()


def create_ticket(db: Session, ticket_obj: Ticket) -> Ticket:


    db.add(ticket_obj)
    try:
        await db.commit()
        await db.refresh(ticket_obj)
    except SQLAlchemyError as e:

        db.rollback()

        logger.exception("Failed to create ticket")
        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {e}")

    return ticket_obj



def update_ticket(db: Session, ticket_id: int, updates) -> Ticket | None:
    """Update a ticket with a mapping or Pydantic model."""
    if isinstance(updates, BaseModel):
        updates = updates.dict(exclude_unset=True)
    ticket = get_ticket(db, ticket_id)

    if not ticket:
        return None
    for key, value in updates.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)
    try:

        db.commit()
        db.refresh(ticket)
        logger.info("Updated ticket %s", ticket_id)
        return ticket
    except Exception:
        db.rollback()
        logger.exception("Failed to update ticket %s", ticket_id)

        raise


async def delete_ticket(db: AsyncSession, ticket_id: int) -> bool:
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return False
    try:

        db.delete(ticket)
        db.commit()
        logger.info("Deleted ticket %s", ticket_id)
        return True
    except Exception:
        db.rollback()
        logger.exception("Failed to delete ticket %s", ticket_id)

        raise


def search_tickets(db: Session, query: str, limit: int = 10) -> list[Ticket]:

    like = f"%{query}%"

    logger.info("Searching tickets for '%s'", query)
    return (
        db.query(Ticket)

        .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
        .limit(limit)
    )


