"""Deprecated - use :mod:`tools.ticket_management` instead."""
from __future__ import annotations

import warnings
from typing import Any, Dict, List, Sequence

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Ticket, VTicketMasterExpanded

from .ticket_management import TicketManager, TicketTools

_manager = TicketManager()


async def get_ticket_expanded(db: AsyncSession, ticket_id: int) -> VTicketMasterExpanded | None:
    warnings.warn(
        "get_ticket_expanded is deprecated; use TicketManager.get_ticket",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_ticket(db, ticket_id)


async def list_tickets_expanded(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    filters: Any | None = None,
    sort: Any | None = None,
) -> Sequence[VTicketMasterExpanded]:
    warnings.warn(
        "list_tickets_expanded is deprecated; use TicketManager.list_tickets",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.list_tickets(db, filters=filters, skip=skip, limit=limit, sort=sort)


async def search_tickets_expanded(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    params: Any | None = None,
) -> List[dict[str, Any]]:
    warnings.warn(
        "search_tickets_expanded is deprecated; use TicketManager.search_tickets",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.search_tickets(db, query=query, limit=limit, params=params)


async def get_tickets_by_user(
    db: AsyncSession,
    identifier: str,
    *,
    skip: int = 0,
    limit: int | None = 100,
    status: str | None = None,
    filters: Dict[str, Any] | None = None,
) -> List[VTicketMasterExpanded]:
    warnings.warn(
        "get_tickets_by_user is deprecated; use TicketManager.get_tickets_by_user",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_tickets_by_user(
        db,
        identifier,
        skip=skip,
        limit=limit,
        status=status,
        filters=filters,
    )


async def tickets_by_timeframe(
    db: AsyncSession,
    *,
    status: str | None = None,
    days: int = 7,
    limit: int = 10,
) -> List[VTicketMasterExpanded]:
    warnings.warn(
        "tickets_by_timeframe is deprecated; use TicketManager.get_tickets_by_timeframe",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_tickets_by_timeframe(db, status=status, days=days, limit=limit)


async def create_ticket(db: AsyncSession, ticket_obj: Ticket | Dict[str, Any]) -> Any:
    warnings.warn(
        "create_ticket is deprecated; use TicketManager.create_ticket",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.create_ticket(db, ticket_obj)


async def update_ticket(db: AsyncSession, ticket_id: int, updates: BaseModel | Dict[str, Any]) -> Ticket | None:
    warnings.warn(
        "update_ticket is deprecated; use TicketManager.update_ticket",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.update_ticket(db, ticket_id, updates)


async def delete_ticket(db: AsyncSession, ticket_id: int) -> bool:
    warnings.warn(
        "delete_ticket is deprecated; use TicketManager.delete_ticket",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.delete_ticket(db, ticket_id)


__all__ = [
    "TicketManager",
    "TicketTools",
    "get_ticket_expanded",
    "list_tickets_expanded",
    "search_tickets_expanded",
    "get_tickets_by_user",
    "tickets_by_timeframe",
    "create_ticket",
    "update_ticket",
    "delete_ticket",
]
