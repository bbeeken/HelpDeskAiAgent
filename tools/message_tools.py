from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from db.models import TicketMessage
from datetime import datetime


def get_ticket_messages(db: Session, ticket_id: int) -> list[TicketMessage]:
    return (
        db.query(TicketMessage)
        .filter(TicketMessage.Ticket_ID == ticket_id)
        .order_by(TicketMessage.DateTimeStamp)
        .all()
    )


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
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save message: {e}")
    return msg
