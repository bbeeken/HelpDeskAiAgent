
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Asset

logger = logging.getLogger(__name__)


async def get_asset(db: AsyncSession, asset_id: int) -> Asset | None:
    result = await db.execute(select(Asset).filter(Asset.ID == asset_id))
    return result.scalars().first()


async def list_assets(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Asset]:
    result = await db.execute(select(Asset).offset(skip).limit(limit))
    return result.scalars().all()


