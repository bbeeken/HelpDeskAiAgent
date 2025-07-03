
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Asset

logger = logging.getLogger(__name__)


async def get_asset(db: AsyncSession, asset_id: int) -> Asset | None:
    return await db.get(Asset, asset_id)


async def list_assets(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Asset]:
    result = await db.execute(
        select(Asset).order_by(Asset.ID).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


