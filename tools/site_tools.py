
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Site

logger = logging.getLogger(__name__)



async def get_site(db: AsyncSession, site_id: int) -> Site | None:
    return await db.get(Site, site_id)


async def list_sites(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Site]:
    result = await db.execute(
        select(Site).order_by(Site.ID).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


