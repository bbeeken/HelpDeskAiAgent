"""Utilities for reading site information from the database."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Site

logger = logging.getLogger(__name__)



async def get_site(db: AsyncSession, site_id: int) -> Site | None:
    """Fetch a site by ID.

    Args:
        db: Async SQLAlchemy session used for the query.
        site_id: Identifier of the site to retrieve.

    Returns:
        The ``Site`` instance if found, otherwise ``None``.
    """

    return await db.get(Site, site_id)


async def list_sites(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Site]:
    """Return a paginated list of sites.

    Args:
        db: Async SQLAlchemy session used for the query.
        skip: Number of records to skip from the beginning.
        limit: Maximum number of records to return.

    Returns:
        A list of ``Site`` instances.
    """

    result = await db.execute(
        select(Site).order_by(Site.ID).offset(skip).limit(limit)
    )
    return list(result.scalars().all())
