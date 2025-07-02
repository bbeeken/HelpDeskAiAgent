from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Ticket


class AnalyticsService:
    """Service providing reporting queries on ticket data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def tickets_by_status(self):
        result = await self.db.execute(
            select(Ticket.Ticket_Status_ID, func.count(Ticket.Ticket_ID)).group_by(
                Ticket.Ticket_Status_ID
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def open_tickets_by_site(self):
        result = await self.db.execute(
            select(Ticket.Site_ID, func.count(Ticket.Ticket_ID))
            .filter(Ticket.Ticket_Status_ID != 3)
            .group_by(Ticket.Site_ID)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def sla_breaches(self, sla_days: int = 2):
        from datetime import datetime, timedelta, UTC

        cutoff = datetime.now(UTC) - timedelta(days=sla_days)
        result = await self.db.execute(
            select(func.count(Ticket.Ticket_ID))
            .filter(Ticket.Created_Date < cutoff)
            .filter(Ticket.Ticket_Status_ID != 3)
        )
        return result.scalar()

    async def open_tickets_by_user(self):
        result = await self.db.execute(
            select(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
            .filter(Ticket.Ticket_Status_ID != 3)
            .group_by(Ticket.Assigned_Email)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def tickets_waiting_on_user(self):
        result = await self.db.execute(
            select(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID))
            .filter(Ticket.Ticket_Status_ID == 4)
            .group_by(Ticket.Ticket_Contact_Email)
        )
        return [(row[0], row[1]) for row in result.all()]
