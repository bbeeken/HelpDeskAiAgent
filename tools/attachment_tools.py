"""Deprecated - use :mod:`tools.ticket_management` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import TicketAttachment

from .ticket_management import TicketManager

_manager = TicketManager()


async def get_ticket_attachments(db: AsyncSession, ticket_id: int) -> list[TicketAttachment]:
    warnings.warn(
        "get_ticket_attachments is deprecated; use TicketManager.get_attachments",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_attachments(db, ticket_id)
