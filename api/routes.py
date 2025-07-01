from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.mssql import SessionLocal

from services.ticket_service import TicketService
from services.analytics_service import AnalyticsService

from tools.asset_tools import get_asset, list_assets
from tools.vendor_tools import get_vendor, list_vendors
from tools.attachment_tools import get_ticket_attachments
from tools.site_tools import get_site, list_sites
from tools.category_tools import list_categories
from tools.status_tools import list_statuses
from tools.message_tools import get_ticket_messages, post_ticket_message
from tools.ai_tools import ai_suggest_response

from pydantic import BaseModel
from typing import List

from schemas.ticket import TicketOut, TicketCreate

from datetime import datetime


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


class MessageIn(BaseModel):
    message: str
    sender_code: str
    sender_name: str


@router.get("/ticket/{ticket_id}", response_model=TicketOut)
def api_get_ticket(ticket_id: int, service: TicketService = Depends(get_ticket_service)):
    ticket = service.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/tickets", response_model=list[TicketOut])
def api_list_tickets(
    skip: int = 0, limit: int = 10, service: TicketService = Depends(get_ticket_service)
):
    return service.list_tickets(skip, limit)




@router.get("/tickets/search", response_model=List[TicketOut])
def api_search_tickets(q: str, limit: int = 10, service: TicketService = Depends(get_ticket_service)):

    return service.search_tickets(q, limit)


@router.post("/ticket", response_model=TicketOut)
def api_create_ticket(ticket: TicketCreate, service: TicketService = Depends(get_ticket_service)):
    from db.models import Ticket

    obj = Ticket(**ticket.dict(), Created_Date=datetime.utcnow())
    created = service.create_ticket(obj)
    return created


@router.put("/ticket/{ticket_id}", response_model=TicketOut)
def api_update_ticket(
    ticket_id: int, updates: dict, service: TicketService = Depends(get_ticket_service)
):
    ticket = service.update_ticket(ticket_id, updates)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.delete("/ticket/{ticket_id}")
def api_delete_ticket(ticket_id: int, service: TicketService = Depends(get_ticket_service)):
    if not service.delete_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"deleted": True}


@router.get("/asset/{asset_id}")
def api_get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/assets")
def api_list_assets(
    skip: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    return list_assets(db, skip, limit)


@router.get("/vendor/{vendor_id}")
def api_get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = get_vendor(db, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.get("/vendors")
def api_list_vendors(
    skip: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    return list_vendors(db, skip, limit)


@router.get("/site/{site_id}")
def api_get_site(site_id: int, db: Session = Depends(get_db)):
    site = get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/sites")
def api_list_sites(
    skip: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    return list_sites(db, skip, limit)


@router.get("/categories")
def api_list_categories(db: Session = Depends(get_db)):
    return list_categories(db)


@router.get("/statuses")
def api_list_statuses(db: Session = Depends(get_db)):
    return list_statuses(db)


@router.get("/ticket/{ticket_id}/attachments")
def api_get_ticket_attachments(
    ticket_id: int, db: Session = Depends(get_db)
):
    return get_ticket_attachments(db, ticket_id)


@router.get("/ticket/{ticket_id}/messages")
def api_get_ticket_messages(
    ticket_id: int, db: Session = Depends(get_db)
):
    return get_ticket_messages(db, ticket_id)


@router.post("/ticket/{ticket_id}/messages")
def api_post_ticket_message(
    ticket_id: int,
    msg: MessageIn,
    db: Session = Depends(get_db),
):
    return post_ticket_message(
        db, ticket_id, msg.message, msg.sender_code, msg.sender_name
    )



@router.post("/ai/suggest_response")
def api_ai_suggest_response(ticket: TicketOut, context: str = ""):
    return {"response": ai_suggest_response(ticket.dict(), context)}


# Analysis endpoints


@router.get("/analytics/status")
def api_tickets_by_status(service: AnalyticsService = Depends(get_analytics_service)):
    return service.tickets_by_status()


@router.get("/analytics/open_by_site")
def api_open_tickets_by_site(service: AnalyticsService = Depends(get_analytics_service)):
    return service.open_tickets_by_site()


@router.get("/analytics/sla_breaches")
def api_sla_breaches(sla_days: int = 2, service: AnalyticsService = Depends(get_analytics_service)):
    return {"breaches": service.sla_breaches(sla_days)}


@router.get("/analytics/open_by_user")
def api_open_tickets_by_user(service: AnalyticsService = Depends(get_analytics_service)):
    return service.open_tickets_by_user()


@router.get("/analytics/waiting_on_user")
def api_tickets_waiting_on_user(service: AnalyticsService = Depends(get_analytics_service)):
    return service.tickets_waiting_on_user()
