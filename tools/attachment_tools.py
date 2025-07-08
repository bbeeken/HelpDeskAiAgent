

"""Helpers for working with ticket attachments."""


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import TicketAttachment

logger = logging.getLogger(__name__)


async def get_ticket_attachments(db: AsyncSession, ticket_id: int) -> list[TicketAttachment]:
    """Return all attachments associated with a ticket.

    Args:
        db: Async SQLAlchemy session used for the query.
        ticket_id: Identifier of the ticket whose attachments are requested.

    Returns:
        A list of ``TicketAttachment`` instances.
    """

    result = await db.execute(
        select(TicketAttachment).filter(TicketAttachment.Ticket_ID == ticket_id)
    )
    return list(result.scalars().all())
