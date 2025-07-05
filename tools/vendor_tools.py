"""Database helpers for retrieving and listing vendor information."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Vendor

logger = logging.getLogger(__name__)



async def get_vendor(db: AsyncSession, vendor_id: int) -> Vendor | None:
    """Retrieve a vendor record by ID.

    Args:
        db: Async SQLAlchemy session used for the query.
        vendor_id: Identifier of the vendor to fetch.

    Returns:
        The ``Vendor`` instance if present, otherwise ``None``.
    """

    return await db.get(Vendor, vendor_id)


async def list_vendors(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Vendor]:
    """Return a paginated list of vendors.

    Args:
        db: Async SQLAlchemy session used for the query.
        skip: Number of records to skip from the beginning.
        limit: Maximum number of records to return.

    Returns:
        A list of ``Vendor`` instances.
    """

    result = await db.execute(
        select(Vendor).order_by(Vendor.ID).offset(skip).limit(limit)
    )
    return list(result.scalars().all())
