from sqlalchemy.orm import Session
from db.models import Vendor


def get_vendor(db: Session, vendor_id: int) -> Vendor | None:
    return db.query(Vendor).filter(Vendor.ID == vendor_id).first()


def list_vendors(db: Session, skip: int = 0, limit: int = 10) -> list[Vendor]:
    return db.query(Vendor).offset(skip).limit(limit).all()
