from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from errors import DatabaseError
from db.models import TicketMessage
from datetime import datetime
import logging

logger = logging.getLogger(__name__)



def get_ticket_messages(db: Session, ticket_id: int) -> list[TicketMessage]:

    return (
        db.query(TicketMessage)

        .filter(TicketMessage.Ticket_ID == ticket_id)
        .order_by(TicketMessage.DateTimeStamp)
    )
    return result.scalars().all()


def post_ticket_message(
    db: Session, ticket_id: int, message: str, sender_code: str, sender_name: str
) -> TicketMessage:

    msg = TicketMessage(
        Ticket_ID=ticket_id,
        Message=message,
        SenderUserCode=sender_code,
        SenderUserName=sender_name,
        DateTimeStamp=datetime.utcnow(),
    )

    db.add(msg)
    try:

        db.commit()
        db.refresh(msg)
        logger.info("Posted message to ticket %s", ticket_id)

    except SQLAlchemyError as e:

        db.rollback()

        logger.exception("Failed to save ticket message for %s", ticket_id)
        raise HTTPException(status_code=500, detail=f"Failed to save message: {e}")

    return msg

