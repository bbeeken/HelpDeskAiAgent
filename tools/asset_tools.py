from sqlalchemy.orm import Session
from db.models import Asset


def get_asset(db: Session, asset_id: int):
    return db.query(Asset).filter(Asset.ID == asset_id).first()


def list_assets(db: Session, skip: int = 0, limit: int = 10):
    query = db.query(Asset)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total
