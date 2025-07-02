from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Asset

logger = logging.getLogger(__name__)


async def get_asset(db: AsyncSession, asset_id: int) -> Asset | None:
    result = await db.execute(select(Asset).where(Asset.ID == asset_id))
    return result.scalar_one_or_none()


async def list_assets(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Asset]:
    result = await db.execute(select(Asset).offset(skip).limit(limit))
    return result.scalars().all()
