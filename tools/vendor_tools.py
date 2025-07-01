from sqlalchemy.orm import Session
import logging
from db.models import Vendor

logger = logging.getLogger(__name__)


def get_vendor(db: Session, vendor_id: int):
    logger.info("Fetching vendor %s", vendor_id)
    return db.query(Vendor).filter(Vendor.ID == vendor_id).first()


def list_vendors(db: Session, skip: int = 0, limit: int = 10):
    logger.info("Listing vendors skip=%s limit=%s", skip, limit)
    return db.query(Vendor).offset(skip).limit(limit).all()

