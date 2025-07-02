import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import TicketAttachment

logger = logging.getLogger(__name__)


async def get_ticket_attachments(db: AsyncSession, ticket_id: int) -> list[TicketAttachment]:
    result = await db.execute(
        select(TicketAttachment).where(TicketAttachment.Ticket_ID == ticket_id)
    )
    return result.scalars().all()
