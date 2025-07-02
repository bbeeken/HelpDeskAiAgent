"""Async helper functions for ticket database operations."""

from __future__ import annotations

import logging
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Ticket


logger = logging.getLogger(__name__)


async def get_ticket(db: AsyncSession, ticket_id: int) -> Ticket | None:
    """Retrieve a ticket by id."""
    return await db.get(Ticket, ticket_id)


async def list_tickets(db: AsyncSession, skip: int = 0, limit: int = 10) -> Sequence[Ticket]:
    """Return a slice of tickets."""
    stmt = select(Ticket).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_ticket(db: AsyncSession, ticket_obj: Ticket) -> Ticket:
    """Persist a new ticket to the database."""
    db.add(ticket_obj)
    try:
        await db.commit()
        await db.refresh(ticket_obj)
        return ticket_obj
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("Failed to create ticket")
        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {exc}")


async def search_tickets(db: AsyncSession, query: str, limit: int = 10) -> Sequence[Ticket]:
    """Search tickets by subject or body."""
    like = f"%{query}%"
    stmt = (
        select(Ticket)
        .where((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_ticket(db: AsyncSession, ticket_id: int, updates: dict) -> Ticket | None:
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return None
    for key, value in updates.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)
    try:
        await db.commit()
        await db.refresh(ticket)
        return ticket
    except SQLAlchemyError:
        await db.rollback()
        raise


async def delete_ticket(db: AsyncSession, ticket_id: int) -> bool:
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return False
    try:
        await db.delete(ticket)
        await db.commit()
        return True
    except SQLAlchemyError:
        await db.rollback()
        raise


def _escape_wildcards(term: str) -> str:
    """Escape SQL wildcard characters."""
    return term.replace("%", "\\%").replace("_", "\\_")

