
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from errors import DatabaseError

from db.models import Ticket
from services.ticket_service import TicketService



async def get_ticket(db: AsyncSession, ticket_id: int):
    return await db.get(Ticket, ticket_id)


async def list_tickets(db: AsyncSession, skip: int = 0, limit: int = 10):
    result = await db.execute(select(Ticket).offset(skip).limit(limit))
    return result.scalars().all()


    query = db.query(Ticket)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


async def create_ticket(db: AsyncSession, ticket_obj: Ticket):

    db.add(ticket_obj)
    try:
        await db.commit()
        await db.refresh(ticket_obj)
    except SQLAlchemyError as e:

        db.rollback()
        raise DatabaseError("Failed to create ticket", str(e))

    return ticket_obj


async def update_ticket(db: AsyncSession, ticket_id: int, updates: dict) -> Ticket | None:
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return None
    for key, value in updates.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)
    try:
        await db.commit()
        await db.refresh(ticket)
        return ticket
    except Exception:
        await db.rollback()
        raise


async def delete_ticket(db: AsyncSession, ticket_id: int) -> bool:
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return False
    try:
        await db.delete(ticket)
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        raise


async def search_tickets(db: AsyncSession, query: str, limit: int = 10):
    like = f"%{query}%"
    result = await db.execute(
        select(Ticket)
        .filter((Ticket.Subject.ilike(like)) | (Ticket.Ticket_Body.ilike(like)))
        .limit(limit)
    )
    return result.scalars().all()

