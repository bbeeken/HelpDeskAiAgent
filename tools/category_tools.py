import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import TicketCategory

logger = logging.getLogger(__name__)


async def list_categories(db: AsyncSession) -> list[TicketCategory]:
    result = await db.execute(select(TicketCategory))
    return result.scalars().all()
