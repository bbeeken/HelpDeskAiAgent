from __future__ import annotations

import logging
from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Ticket

logger = logging.getLogger(__name__)


async def tickets_by_status(db: AsyncSession) -> list[tuple[int | None, int]]:
    logger.info("Calculating tickets by status")
    result = await db.execute(
        select(Ticket.Ticket_Status_ID, func.count(Ticket.Ticket_ID)).group_by(
            Ticket.Ticket_Status_ID
        )
    )
    return [(row[0], row[1]) for row in result.all()]


async def open_tickets_by_site(db: AsyncSession) -> list[tuple[int | None, int]]:
    logger.info("Calculating open tickets by site")
    result = await db.execute(
        select(Ticket.Site_ID, func.count(Ticket.Ticket_ID))
        .where(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Site_ID)
    )
    return [(row[0], row[1]) for row in result.all()]


async def sla_breaches(db: AsyncSession, sla_days: int = 2) -> int:
    logger.info("Counting SLA breaches older than %s days", sla_days)
    cutoff = datetime.utcnow() - timedelta(days=sla_days)
    result = await db.execute(
        select(func.count(Ticket.Ticket_ID))
        .where(Ticket.Created_Date < cutoff)
        .where(Ticket.Ticket_Status_ID != 3)
    )
    return result.scalar_one()


async def open_tickets_by_user(db: AsyncSession) -> list[tuple[str | None, int]]:
    logger.info("Calculating open tickets by user")
    result = await db.execute(
        select(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
        .where(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Assigned_Email)
    )
    return [(row[0], row[1]) for row in result.all()]


async def tickets_waiting_on_user(db: AsyncSession) -> list[tuple[str | None, int]]:
    logger.info("Calculating tickets waiting on user")
    result = await db.execute(
        select(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID))
        .where(Ticket.Ticket_Status_ID == 4)
        .group_by(Ticket.Ticket_Contact_Email)
    )
    return [(row[0], row[1]) for row in result.all()]
