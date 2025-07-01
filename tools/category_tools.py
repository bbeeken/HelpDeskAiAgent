
from sqlalchemy.orm import Session
import logging

from db.models import TicketCategory

logger = logging.getLogger(__name__)


def list_categories(db: Session) -> list[TicketCategory]:

    return db.query(TicketCategory).all()

