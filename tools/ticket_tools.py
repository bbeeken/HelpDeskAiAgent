
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException
import logging

from db.models import Ticket
from services.ticket_service import TicketService



async def get_ticket(db: AsyncSession, ticket_id: int):
    return await db.get(Ticket, ticket_id)

logger = logging.getLogger(__name__)



def get_ticket(db: Session, ticket_id: int):
    logger.info("Fetching ticket %s", ticket_id)
    return db.query(Ticket).filter(Ticket.Ticket_ID == ticket_id).first()


def list_tickets(db: Session, skip: int = 0, limit: int = 10):
    logger.info("Listing tickets skip=%s limit=%s", skip, limit)
    return db.query(Ticket).offset(skip).limit(limit).all()


def create_ticket(db: Session, ticket_obj: Ticket):
    logger.info("Creating ticket")


    db.add(ticket_obj)
    try:
        await db.commit()
        await db.refresh(ticket_obj)
    except SQLAlchemyError as e:

        db.rollback()

        logger.exception("Failed to create ticket")
        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {e}")

    return ticket_obj


async def update_ticket(db: AsyncSession, ticket_id: int, updates: dict) -> Ticket | None:
    ticket = await get_ticket(db, ticket_id)
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


async def search_tickets(db: AsyncSession, query: str, limit: int = 10):
    like = f"%{query}%"

    logger.info("Searching tickets for '%s'", query)
    return (
        db.query(Ticket)

        .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
        .limit(limit)
    )


