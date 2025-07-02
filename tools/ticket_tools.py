import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from pydantic import BaseModel
from db.models import Ticket

logger = logging.getLogger(__name__)


async def get_ticket(db: AsyncSession, ticket_id: int) -> Ticket | None:
    result = await db.execute(select(Ticket).filter(Ticket.Ticket_ID == ticket_id))
    return result.scalars().first()


async def list_tickets(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Ticket]:
    result = await db.execute(select(Ticket).offset(skip).limit(limit))
    return result.scalars().all()


async def create_ticket(db: AsyncSession, ticket_obj: Ticket) -> Ticket:
    db.add(ticket_obj)
    try:
        await db.commit()
        await db.refresh(ticket_obj)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception("Failed to create ticket")
        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {e}")
    return ticket_obj


async def update_ticket(db: AsyncSession, ticket_id: int, updates: Any) -> Ticket | None:
    if isinstance(updates, BaseModel):
        updates = updates.dict(exclude_unset=True)
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return None
    for key, value in updates.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)
    try:
        await db.commit()
        await db.refresh(ticket)
        logger.info("Updated ticket %s", ticket_id)
        return ticket
    except Exception:
        await db.rollback()
        logger.exception("Failed to update ticket %s", ticket_id)
        raise


async def delete_ticket(db: AsyncSession, ticket_id: int) -> bool:
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return False
    try:
        await db.delete(ticket)
        await db.commit()
        logger.info("Deleted ticket %s", ticket_id)
        return True
    except Exception:
        await db.rollback()
        logger.exception("Failed to delete ticket %s", ticket_id)
        raise


async def search_tickets(db: AsyncSession, query: str, limit: int = 10) -> list[Ticket]:
    like = f"%{query}%"
    logger.info("Searching tickets for '%s'", query)
    stmt = (
        select(Ticket)
        .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
