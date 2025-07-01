from sqlalchemy.orm import Session
from db.models import Site

def get_site(db: Session, site_id: int):
    return db.query(Site).filter(Site.ID == site_id).first()

def list_sites(db: Session, skip: int = 0, limit: int = 10):
    return db.query(Site).offset(skip).limit(limit).all()
