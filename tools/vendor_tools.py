"""Deprecated - use :mod:`tools.reference_data` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Vendor

from .reference_data import ReferenceDataManager

_manager = ReferenceDataManager()


async def get_vendor(db: AsyncSession, vendor_id: int) -> Vendor | None:
    warnings.warn(
        "get_vendor is deprecated; use ReferenceDataManager.get_vendor",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_vendor(db, vendor_id)


async def list_vendors(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Vendor]:
    warnings.warn(
        "list_vendors is deprecated; use ReferenceDataManager.list_vendors",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.list_vendors(db, skip=skip, limit=limit)
