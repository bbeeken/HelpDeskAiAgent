from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Site

logger = logging.getLogger(__name__)


async def get_site(db: AsyncSession, site_id: int) -> Site | None:
    result = await db.execute(select(Site).where(Site.ID == site_id))
    return result.scalar_one_or_none()


async def list_sites(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Site]:
    result = await db.execute(select(Site).offset(skip).limit(limit))
    return result.scalars().all()
