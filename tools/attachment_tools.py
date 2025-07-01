
from sqlalchemy.orm import Session
import logging

from db.models import TicketAttachment

logger = logging.getLogger(__name__)


def get_ticket_attachments(db: Session, ticket_id: int) -> list[TicketAttachment]:

    return db.query(TicketAttachment).filter(TicketAttachment.Ticket_ID == ticket_id).all()

