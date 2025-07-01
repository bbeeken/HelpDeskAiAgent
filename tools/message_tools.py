from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from db.models import TicketMessage
from datetime import datetime


async def get_ticket_messages(db: AsyncSession, ticket_id: int):
    result = await db.execute(
        select(TicketMessage)
        .filter(TicketMessage.Ticket_ID == ticket_id)
        .order_by(TicketMessage.DateTimeStamp)
    )
    return result.scalars().all()


async def post_ticket_message(
    db: AsyncSession, ticket_id: int, message: str, sender_code: str, sender_name: str
):
    msg = TicketMessage(
        Ticket_ID=ticket_id,
        Message=message,
        SenderUserCode=sender_code,
        SenderUserName=sender_name,
        DateTimeStamp=datetime.utcnow(),
    )

    db.add(msg)
    try:
        await db.commit()
        await db.refresh(msg)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save message: {e}")
    return msg
