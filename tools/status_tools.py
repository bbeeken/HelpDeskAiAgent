"""Deprecated - use :mod:`tools.reference_data` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import TicketStatus
from typing import Any

from .reference_data import ReferenceDataManager

_manager = ReferenceDataManager()


async def list_statuses(
    db: AsyncSession,
    filters: dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> list[TicketStatus]:
    warnings.warn(
        "list_statuses is deprecated; use ReferenceDataManager.list_statuses",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.list_statuses(db, filters=filters, sort=sort)
