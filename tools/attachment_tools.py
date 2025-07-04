"""Helpers for retrieving ticket attachment records from the database."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import TicketAttachment

logger = logging.getLogger(__name__)


async def get_ticket_attachments(db: AsyncSession, ticket_id: int) -> list[TicketAttachment]:
    result = await db.execute(
        select(TicketAttachment).filter(TicketAttachment.Ticket_ID == ticket_id)
    )
    return list(result.scalars().all())
