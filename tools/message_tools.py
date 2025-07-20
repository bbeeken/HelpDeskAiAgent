"""Deprecated - use :mod:`tools.ticket_management` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TicketMessage

from .ticket_management import TicketManager

_manager = TicketManager()


async def get_ticket_messages(db: AsyncSession, ticket_id: int) -> list[TicketMessage]:
    warnings.warn(
        "get_ticket_messages is deprecated; use TicketManager.get_messages",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_messages(db, ticket_id)


async def post_ticket_message(
    db: AsyncSession,
    ticket_id: int,
    message: str,
    sender_code: str,
    sender_name: str,
) -> TicketMessage:
    warnings.warn(
        "post_ticket_message is deprecated; use TicketManager.post_message",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.post_message(db, ticket_id, message, sender_code, sender_name)
