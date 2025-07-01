from sqlalchemy.orm import Session
import logging
from db.models import Site

logger = logging.getLogger(__name__)


def get_site(db: Session, site_id: int):
    logger.info("Fetching site %s", site_id)
    return db.query(Site).filter(Site.ID == site_id).first()


def list_sites(db: Session, skip: int = 0, limit: int = 10):
    logger.info("Listing sites skip=%s limit=%s", skip, limit)
    return db.query(Site).offset(skip).limit(limit).all()

