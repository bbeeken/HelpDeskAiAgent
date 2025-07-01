from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.mssql import SessionLocal, engine
from sqlalchemy import text


from services.ticket_service import TicketService
from services.analytics_service import AnalyticsService

from tools.ticket_tools import (
    get_ticket,
    list_tickets,
    create_ticket,
    update_ticket,
    delete_ticket,
    search_tickets,
    _escape_wildcards,
)


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
from schemas.paginated import PaginatedResponse

from schemas.ticket import TicketOut, TicketCreate

from datetime import datetime

APP_VERSION = "0.1.0"
START_TIME = datetime.utcnow()



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

    class Config:
        schema_extra = {
            "example": {
                "message": "Thanks for the update",
                "sender_code": "USR123",
                "sender_name": "John Doe",
            }
        }


@router.get("/ticket/{ticket_id}", response_model=TicketOut)
def api_get_ticket(ticket_id: int, service: TicketService = Depends(get_ticket_service)):
    ticket = service.get_ticket(ticket_id)


@router.get("/ticket/{ticket_id}", response_model=TicketOut, tags=["Tickets"])
def api_get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Retrieve a single ticket by its ID."""
    ticket = get_ticket(db, ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket



@router.get("/tickets", response_model=PaginatedResponse[TicketOut])


def api_list_tickets(
    skip: int = 0, limit: int = 10, service: TicketService = Depends(get_ticket_service)
):

    items, total = list_tickets(db, skip, limit)
    return PaginatedResponse[TicketOut](
        items=items, total=total, skip=skip, limit=limit
    )





@router.get("/tickets/search", response_model=List[TicketOut])
def api_search_tickets(q: str, limit: int = 10, service: TicketService = Depends(get_ticket_service)):

    return service.search_tickets(q, limit)


@router.post("/ticket", response_model=TicketOut)
def api_create_ticket(ticket: TicketCreate, service: TicketService = Depends(get_ticket_service)):

    """Return a paginated list of tickets."""
    return list_tickets(db, skip, limit)




@router.get("/tickets/search", response_model=List[TicketOut], tags=["Tickets"])
def api_search_tickets(q: str, limit: int = 10, db: Session = Depends(get_db)):

    return search_tickets(db, _escape_wildcards(q), limit)



@router.post("/ticket", response_model=TicketOut, tags=["Tickets"])
def api_create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    """Create a new ticket and return the created record."""

    from db.models import Ticket

    obj = Ticket(**ticket.dict(), Created_Date=datetime.utcnow())
    created = service.create_ticket(obj)
    return created


@router.put("/ticket/{ticket_id}", response_model=TicketOut, tags=["Tickets"])
def api_update_ticket(
    ticket_id: int, updates: dict, service: TicketService = Depends(get_ticket_service)
):

    ticket = service.update_ticket(ticket_id, updates)

    """Update an existing ticket with a dictionary of fields."""
    ticket = update_ticket(db, ticket_id, updates)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket



@router.delete("/ticket/{ticket_id}")
def api_delete_ticket(ticket_id: int, service: TicketService = Depends(get_ticket_service)):
    if not service.delete_ticket(ticket_id):

@router.delete("/ticket/{ticket_id}", tags=["Tickets"])
def api_delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Delete a ticket by ID."""
    if not delete_ticket(db, ticket_id):

        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"deleted": True}


@router.get("/asset/{asset_id}", tags=["Assets"])
def api_get_asset(asset_id: int, db: Session = Depends(get_db)):
    """Retrieve a single asset by ID."""
    asset = get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset



@router.get("/assets", response_model=PaginatedResponse[dict])
def api_list_assets(
    skip: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    items, total = list_assets(db, skip, limit)
    return PaginatedResponse(
        items=items, total=total, skip=skip, limit=limit
    )



@router.get("/vendor/{vendor_id}", tags=["Vendors"])
def api_get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    """Retrieve a vendor record by ID."""
    vendor = get_vendor(db, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor



@router.get("/vendors", response_model=PaginatedResponse[dict])
def api_list_vendors(
    skip: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    items, total = list_vendors(db, skip, limit)
    return PaginatedResponse(
        items=items, total=total, skip=skip, limit=limit
    )



@router.get("/site/{site_id}", tags=["Sites"])
def api_get_site(site_id: int, db: Session = Depends(get_db)):
    """Get a site record by ID."""
    site = get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site



@router.get("/sites", response_model=PaginatedResponse[dict])
def api_list_sites(
    skip: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    items, total = list_sites(db, skip, limit)
    return PaginatedResponse(
        items=items, total=total, skip=skip, limit=limit
    )



@router.get("/categories", tags=["Metadata"])
def api_list_categories(db: Session = Depends(get_db)):
    """Return available ticket categories."""
    return list_categories(db)


@router.get("/statuses", tags=["Metadata"])
def api_list_statuses(db: Session = Depends(get_db)):
    """Return available status values."""
    return list_statuses(db)


@router.get("/ticket/{ticket_id}/attachments", tags=["Attachments"])
def api_get_ticket_attachments(
    ticket_id: int, db: Session = Depends(get_db)
):
    """List attachments associated with a ticket."""
    return get_ticket_attachments(db, ticket_id)


@router.get("/ticket/{ticket_id}/messages", tags=["Messages"])
def api_get_ticket_messages(
    ticket_id: int, db: Session = Depends(get_db)
):
    """Return the message thread for a ticket."""
    return get_ticket_messages(db, ticket_id)


@router.post("/ticket/{ticket_id}/messages", tags=["Messages"])
def api_post_ticket_message(
    ticket_id: int,
    msg: MessageIn,
    db: Session = Depends(get_db),
):
    """Add a new message to a ticket conversation."""
    return post_ticket_message(
        db, ticket_id, msg.message, msg.sender_code, msg.sender_name
    )



@router.post("/ai/suggest_response", tags=["AI"])
def api_ai_suggest_response(ticket: TicketOut, context: str = ""):
    """Generate an AI suggested response for the provided ticket."""
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

@router.get("/analytics/status", tags=["Analytics"])
def api_tickets_by_status(db: Session = Depends(get_db)):
    """Return ticket counts grouped by status."""
    return tickets_by_status(db)


@router.get("/analytics/open_by_site", tags=["Analytics"])
def api_open_tickets_by_site(db: Session = Depends(get_db)):
    """Return counts of open tickets grouped by site."""
    return open_tickets_by_site(db)


@router.get("/analytics/sla_breaches", tags=["Analytics"])
def api_sla_breaches(sla_days: int = 2, db: Session = Depends(get_db)):
    """Return the number of tickets that exceeded the SLA."""
    return {"breaches": sla_breaches(db, sla_days)}


@router.get("/analytics/open_by_user", tags=["Analytics"])
def api_open_tickets_by_user(db: Session = Depends(get_db)):
    """Return counts of open tickets grouped by assigned user."""
    return open_tickets_by_user(db)


@router.get("/analytics/waiting_on_user", tags=["Analytics"])
def api_tickets_waiting_on_user(db: Session = Depends(get_db)):
    """Return counts of tickets waiting on a user response."""
    return tickets_waiting_on_user(db)


@router.get("/health")
def api_health():
    """Return application health information."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    uptime = (datetime.utcnow() - START_TIME).total_seconds()
    return {
        "status": "ok",
        "db": db_status,
        "uptime": uptime,
        "version": APP_VERSION,
    }
