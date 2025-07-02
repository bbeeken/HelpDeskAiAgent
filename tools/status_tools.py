
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import TicketStatus

logger = logging.getLogger(__name__)


async def list_statuses(db: AsyncSession) -> list[TicketStatus]:
    result = await db.execute(select(TicketStatus))
    return result.scalars().all()


