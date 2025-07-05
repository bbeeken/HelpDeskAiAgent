"""Database helpers for reading and posting ticket messages."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException

from db.models import TicketMessage
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)




async def get_ticket_messages(db: AsyncSession, ticket_id: int) -> list[TicketMessage]:
    """Retrieve all messages for a ticket ordered chronologically.

    Args:
        db: Async SQLAlchemy session used for the query.
        ticket_id: Identifier of the ticket whose messages are requested.

    Returns:
        A list of ``TicketMessage`` instances sorted by timestamp.
    """

    result = await db.execute(
        select(TicketMessage)
        .filter(TicketMessage.Ticket_ID == ticket_id)
        .order_by(TicketMessage.DateTimeStamp)
    )
    return list(result.scalars().all())


async def post_ticket_message(
    db: AsyncSession, ticket_id: int, message: str, sender_code: str, sender_name: str
) -> TicketMessage:
    """Persist a new message to a ticket.

    Args:
        db: Async SQLAlchemy session used for the insert.
        ticket_id: Identifier of the ticket to post to.
        message: Body text of the ticket message.
        sender_code: User code of the sender.
        sender_name: Display name of the sender.

    Returns:
        The saved ``TicketMessage`` instance.
    """

    msg = TicketMessage(
        Ticket_ID=ticket_id,
        Message=message,
        SenderUserCode=sender_code,
        SenderUserName=sender_name,
        DateTimeStamp=datetime.now(UTC),
    )

    db.add(msg)
    try:
        await db.commit()
        await db.refresh(msg)
        logger.info("Posted message to ticket %s", ticket_id)

    except SQLAlchemyError as e:
        await db.rollback()

        logger.exception("Failed to save ticket message for %s", ticket_id)
        raise HTTPException(status_code=500, detail=f"Failed to save message: {e}")

    return msg
