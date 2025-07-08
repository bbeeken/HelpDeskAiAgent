"""Database helpers for retrieving and listing asset information."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Asset

logger = logging.getLogger(__name__)


async def get_asset(db: AsyncSession, asset_id: int) -> Asset | None:
    """Retrieve a single asset by its primary key.

    Args:
        db: Async SQLAlchemy session used for the query.
        asset_id: Identifier of the asset to fetch.

    Returns:
        The ``Asset`` instance if found, otherwise ``None``.
    """

    return await db.get(Asset, asset_id)


async def list_assets(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Asset]:
    """Return a paginated list of assets ordered by ID.

    Args:
        db: Async SQLAlchemy session used for the query.
        skip: Number of records to skip from the beginning.
        limit: Maximum number of records to return.

    Returns:
        A list of ``Asset`` instances.
    """

    result = await db.execute(
        select(Asset).order_by(Asset.ID).offset(skip).limit(limit)
    )
    return list(result.scalars().all())
