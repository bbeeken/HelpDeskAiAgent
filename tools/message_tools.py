from sqlalchemy.orm import Session
from db.models import TicketMessage
from datetime import datetime

def get_ticket_messages(db: Session, ticket_id: int):
    return (
        db.query(TicketMessage)
        .filter(TicketMessage.Ticket_ID == ticket_id)
        .order_by(TicketMessage.DateTimeStamp)
        .all()
    )

def post_ticket_message(db: Session, ticket_id: int, message: str, sender_code: str, sender_name: str):
    msg = TicketMessage(
        Ticket_ID=ticket_id,
        Message=message,
        SenderUserCode=sender_code,
        SenderUserName=sender_name,
        DateTimeStamp=datetime.utcnow()
    )
    try:
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg
    except Exception:
        db.rollback()
        raise
