
from sqlalchemy.orm import Session
import logging

from db.models import TicketCategory

logger = logging.getLogger(__name__)



def list_categories(db: Session):
    logger.info("Listing categories")
    return db.query(TicketCategory).all()

