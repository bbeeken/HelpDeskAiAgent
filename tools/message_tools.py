"""Async helpers for ticket message operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TicketMessage


logger = logging.getLogger(__name__)


async def get_ticket_messages(db: AsyncSession, ticket_id: int) -> Sequence[TicketMessage]:
    stmt = (
        select(TicketMessage)
        .where(TicketMessage.Ticket_ID == ticket_id)
        .order_by(TicketMessage.DateTimeStamp)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def post_ticket_message(
    db: AsyncSession,
    ticket_id: int,
    message: str,
    sender_code: str,
    sender_name: str,
) -> TicketMessage:
    msg = TicketMessage(
        Ticket_ID=ticket_id,
        Message=message,
        SenderUserCode=sender_code,
        SenderUserName=sender_name,
        DateTimeStamp=datetime.utcnow(),
    )
    db.add(msg)
    try:
        await db.commit()
        await db.refresh(msg)
        logger.info("Posted message to ticket %s", ticket_id)
        return msg
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("Failed to save ticket message for %s", ticket_id)
        raise HTTPException(status_code=500, detail=f"Failed to save message: {exc}")

