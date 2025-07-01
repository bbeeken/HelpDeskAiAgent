
from sqlalchemy.orm import Session
import logging

from db.models import Asset

logger = logging.getLogger(__name__)


def get_asset(db: Session, asset_id: int) -> Asset | None:
    return db.query(Asset).filter(Asset.ID == asset_id).first()


def list_assets(db: Session, skip: int = 0, limit: int = 10) -> list[Asset]:

    return db.query(Asset).offset(skip).limit(limit).all()


