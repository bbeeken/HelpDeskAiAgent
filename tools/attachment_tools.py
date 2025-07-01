from sqlalchemy.orm import Session
from db.models import TicketAttachment


def get_ticket_attachments(db: Session, ticket_id: int) -> list[TicketAttachment]:
    return db.query(TicketAttachment).filter(TicketAttachment.Ticket_ID == ticket_id).all()
