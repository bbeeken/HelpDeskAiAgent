from sqlalchemy.orm import Session
from db.models import Vendor


def get_vendor(db: Session, vendor_id: int):
    return db.query(Vendor).filter(Vendor.ID == vendor_id).first()


def list_vendors(db: Session, skip: int = 0, limit: int = 10):
    query = db.query(Vendor)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total
