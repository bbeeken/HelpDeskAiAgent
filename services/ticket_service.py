from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from db.models import Ticket, VTicketMasterExpanded


class TicketService:
    """Service class providing ticket-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_ticket(self, ticket_id: int) -> VTicketMasterExpanded | None:
        return await self.db.get(VTicketMasterExpanded, ticket_id)

    async def list_tickets(self, skip: int = 0, limit: int = 10) -> list[VTicketMasterExpanded]:
        result = await self.db.execute(select(VTicketMasterExpanded).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create_ticket(self, ticket_obj: Ticket) -> Ticket:
        self.db.add(ticket_obj)
        try:
            await self.db.commit()
            await self.db.refresh(ticket_obj)
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create ticket: {e}")
        return ticket_obj

    async def update_ticket(self, ticket_id: int, updates: dict):
        ticket = await self.get_ticket(ticket_id)
        if not ticket:
            return None
        for key, value in updates.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        try:
            await self.db.commit()
            await self.db.refresh(ticket)
            return ticket
        except Exception:
            await self.db.rollback()
            raise

    async def delete_ticket(self, ticket_id: int) -> bool:
        ticket = await self.get_ticket(ticket_id)
        if not ticket:
            return False
        try:
            await self.db.delete(ticket)
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            raise

    async def search_tickets(self, query: str, limit: int = 10) -> list[VTicketMasterExpanded]:
        like = f"%{query}%"
        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .filter(
                (VTicketMasterExpanded.Subject.ilike(like))
                | (VTicketMasterExpanded.Ticket_Body.ilike(like))
            )
            .limit(limit)
        )
        return list(result.scalars().all())
