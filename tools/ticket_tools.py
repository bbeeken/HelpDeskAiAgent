from __future__ import annotations

import logging
from typing import Sequence, Mapping, Any

from sqlalchemy import select, text

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Ticket


logger = logging.getLogger(__name__)


async def get_ticket(db: AsyncSession, ticket_id: int) -> Ticket | None:
    return await db.get(Ticket, ticket_id)


async def list_tickets(
    db: AsyncSession, skip: int = 0, limit: int = 10
) -> Sequence[Ticket]:
    result = await db.execute(select(Ticket).offset(skip).limit(limit))
    return result.scalars().all()

async def list_tickets_expanded(
    db: AsyncSession, skip: int = 0, limit: int = 10


) -> Sequence[Mapping[str, Any]]:
    """Return tickets with related labels from the expanded view."""

    result = await db.execute(
        text(
            "SELECT * FROM V_Ticket_Master_Expanded LIMIT :limit OFFSET :skip"
        ),
        {"limit": limit, "skip": skip},
    )

    return [dict(row._mapping) for row in result]




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


async def update_ticket(db: AsyncSession, ticket_id: int, updates) -> Ticket | None:
    """Update a ticket with a mapping or Pydantic model."""
    if isinstance(updates, BaseModel):
        updates = updates.dict(exclude_unset=True)


    ticket = await db.get(Ticket, ticket_id)
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

    ticket = await db.get(Ticket, ticket_id)
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


async def search_tickets(
    db: AsyncSession, query: str, limit: int = 10
) -> Sequence[Ticket]:
    like = f"%{query}%"
    logger.info("Searching tickets for '%s'", query)
    result = await db.execute(
        select(Ticket)
        .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
        .limit(limit)
    )
    return result.scalars().all()
