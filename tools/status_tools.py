
from sqlalchemy.orm import Session
import logging

from db.models import TicketStatus

logger = logging.getLogger(__name__)


def list_statuses(db: Session) -> list[TicketStatus]:


    return db.query(TicketStatus).all()


