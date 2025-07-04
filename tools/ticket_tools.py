"""Database helpers for manipulating tickets."""

from __future__ import annotations

import logging
from typing import Any, Sequence

from sqlalchemy import select
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Ticket, VTicketMasterExpanded

logger = logging.getLogger(__name__)


async def get_ticket_expanded(
    db: AsyncSession, ticket_id: int
) -> VTicketMasterExpanded | None:
    """Return a ticket from the expanded view."""
    return await db.get(VTicketMasterExpanded, ticket_id)



async def list_tickets_expanded(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    filters: dict[str, Any] | None = None,
    sort: str | list[str] | None = None,
) -> Sequence[VTicketMasterExpanded]:
    """Return tickets with related labels from the expanded view."""

    query = select(VTicketMasterExpanded)

    if filters:
        for key, value in filters.items():
            if hasattr(VTicketMasterExpanded, key):
                query = query.filter(getattr(VTicketMasterExpanded, key) == value)

    if sort:
        if isinstance(sort, str):
            sort = [sort]

        order_columns = []
        for s in sort:
            direction = "asc"
            column = s
            if s.startswith("-"):
                column = s[1:]
                direction = "desc"
            elif " " in s:
                column, dir_part = s.rsplit(" ", 1)
                if dir_part.lower() in {"asc", "desc"}:
                    direction = dir_part.lower()
            if hasattr(VTicketMasterExpanded, column):
                attr = getattr(VTicketMasterExpanded, column)
                order_columns.append(
                    attr.desc() if direction == "desc" else attr.asc()
                )
        if order_columns:
            query = query.order_by(*order_columns)
    else:
        query = query.order_by(VTicketMasterExpanded.Ticket_ID)

    if skip:
        query = query.offset(skip)
    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def search_tickets_expanded(
    db: AsyncSession, query: str, limit: int = 10
) -> Sequence[VTicketMasterExpanded]:
    """Search tickets in the expanded view by subject or body."""
    like = f"%{query}%"

    result = await db.execute(
        select(VTicketMasterExpanded)
        .filter(
            (VTicketMasterExpanded.Subject.ilike(like))
            | (VTicketMasterExpanded.Ticket_Body.ilike(like))
        )
        .limit(limit)
    )
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
