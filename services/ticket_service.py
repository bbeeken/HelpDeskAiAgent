from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from db.models import Ticket


class TicketService:
    """Service class providing ticket-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_ticket(self, ticket_id: int):
        result = await self.db.execute(
            select(Ticket).filter(Ticket.Ticket_ID == ticket_id)
        )
        return result.scalars().first()

    async def list_tickets(self, skip: int = 0, limit: int = 10):
        result = await self.db.execute(
            select(Ticket).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create_ticket(self, ticket_obj: Ticket):
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

    async def search_tickets(self, query: str, limit: int = 10):
        like = f"%{query}%"
        stmt = (
            select(Ticket)
            .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
