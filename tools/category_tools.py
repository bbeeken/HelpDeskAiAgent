"""Deprecated - use :mod:`tools.reference_data` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import TicketCategory
from typing import Any

from .reference_data import ReferenceDataManager

_manager = ReferenceDataManager()


async def list_categories(
    db: AsyncSession,
    filters: dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> list[TicketCategory]:
    warnings.warn(
        "list_categories is deprecated; use ReferenceDataManager.list_categories",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.list_categories(db, filters=filters, sort=sort)
