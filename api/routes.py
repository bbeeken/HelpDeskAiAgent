# routers.py

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.mssql import SessionLocal
from db.models import Ticket, VTicketMasterExpanded
from limiter import limiter

# Tool imports
from tools.asset_tools import get_asset, list_assets
from tools.attachment_tools import get_ticket_attachments
from tools.analysis_tools import (
    open_tickets_by_site,
    open_tickets_by_user,
    sla_breaches,
    tickets_by_status,
    tickets_waiting_on_user,
)
from tools.ai_tools import ai_stream_response, ai_suggest_response
from tools.message_tools import get_ticket_messages, post_ticket_message
from tools.oncall_tools import get_current_oncall
from tools.site_tools import get_site, list_sites
from tools.status_tools import list_statuses
from tools.category_tools import list_categories
from tools.ticket_tools import (
    create_ticket,
    delete_ticket,
    get_ticket_expanded,
    list_tickets_expanded,
    search_tickets_expanded,
)
from tools.vendor_tools import get_vendor, list_vendors

# Schema imports
from schemas.analytic import (
    SiteOpenCount,
    StatusCount,
    UserOpenCount,
    WaitingOnUserCount,
)
from schemas.basic import (
    AssetOut,
    SiteOut,
    TicketAttachmentOut,
    TicketMessageOut,
    TicketStatusOut,
    TicketCategoryOut,
    VendorOut,
)
from schemas.oncall import OnCallShiftOut
from schemas.paginated import PaginatedResponse
from schemas.ticket import TicketCreate, TicketExpandedOut, TicketOut, TicketUpdate

logger = logging.getLogger(__name__)

# --- Dependencies & Helpers --------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session and ensures it is closed."""
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

def extract_filters(
    request: Request, 
    exclude: List[str] = ("skip", "limit", "sort")
) -> Dict[str, Any]:
    """Pull out query params to use as equality filters."""
    return {
        key: value
        for key, value in request.query_params.multi_items()
        if key not in exclude
    }

# Pagination parameters dependency
def pagination_params(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, int]:
    return {"skip": skip, "limit": limit}

# --- Main Router & Sub-Routers -----------------------------------------------

router = APIRouter()

# Ticket sub-router
ticket_router = APIRouter(prefix="/ticket", tags=["tickets"])

class MessageIn(BaseModel):
    message: str = Field(..., example="Thanks for the update")
    sender_code: str = Field(..., example="USR123")
    sender_name: str = Field(..., example="John Doe")

@ticket_router.get("/{ticket_id}", response_model=TicketExpandedOut)
async def get_ticket(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> TicketExpandedOut:
    ticket = await get_ticket_expanded(db, ticket_id)
    if not ticket:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(404, "Ticket not found")
    return ticket

@ticket_router.post("", response_model=TicketOut)
async def create_new_ticket(
    data: TicketCreate, db: AsyncSession = Depends(get_db)
) -> TicketOut:
    obj = Ticket(**data.model_dump(), Created_Date=datetime.now(timezone.utc))
    created = await create_ticket(db, obj)
    return created

@ticket_router.put("/{ticket_id}", response_model=TicketOut)
async def update_existing_ticket(
    ticket_id: int, updates: TicketUpdate, db: AsyncSession = Depends(get_db)
) -> TicketOut:
    updated = await update_ticket(db, ticket_id, updates)
    if not updated:
        logger.warning("Ticket %s not found for update", ticket_id)
        raise HTTPException(404, "Ticket not found")
    return updated

@ticket_router.delete("/{ticket_id}", response_model=Dict[str, bool])
async def delete_existing_ticket(
    ticket_id: int, db: AsyncSession = Depends(get_db)
):
    success = await delete_ticket(db, ticket_id)
    if not success:
        logger.warning("Ticket %s not found for delete", ticket_id)
        raise HTTPException(404, "Ticket not found")
    return {"deleted": True}

# Message endpoints
@ticket_router.get("/{ticket_id}/messages", response_model=List[TicketMessageOut])
async def list_ticket_messages(
    ticket_id: int, db: AsyncSession = Depends(get_db)
):
    msgs = await get_ticket_messages(db, ticket_id)
    return [TicketMessageOut.model_validate(m) for m in msgs]

@ticket_router.post("/{ticket_id}/messages", response_model=TicketMessageOut)
async def add_ticket_message(
    ticket_id: int,
    msg: MessageIn,
    db: AsyncSession = Depends(get_db),
) -> TicketMessageOut:
    created = await post_ticket_message(
        db, ticket_id, msg.message, msg.sender_code, msg.sender_name
    )
    return TicketMessageOut.model_validate(created)

# Search & list
@ticket_router.get("/search", response_model=List[TicketExpandedOut])
async def search_tickets(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    results = await search_tickets_expanded(db, q, limit)
    return [TicketExpandedOut.model_validate(r) for r in results]

@router.get("/tickets", response_model=PaginatedResponse[TicketExpandedOut], tags=["tickets"])
async def list_tickets(
    request: Request,
    pagination: Dict[str, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    filters = extract_filters(request)
    items = await list_tickets_expanded(
        db, pagination["skip"], pagination["limit"], filters=filters or None
    )

    count_q = select(func.count(VTicketMasterExpanded.Ticket_ID))
    for k, v in filters.items():
        if hasattr(VTicketMasterExpanded, k):
            count_q = count_q.filter(getattr(VTicketMasterExpanded, k) == v)
    total = await db.scalar(count_q) or 0

    validated = [TicketExpandedOut.model_validate(t) for t in items]
    return PaginatedResponse(items=validated, total=total, **pagination)

router.include_router(ticket_router)

# Asset, Vendor, Site, Category, Status routers (grouped similarly)

basic_router = APIRouter(tags=["lookup"])

@basic_router.get("/assets", response_model=List[AssetOut])
async def get_assets(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
):
    assets = await list_assets(db, skip, limit)
    return [AssetOut.model_validate(a) for a in assets]

@basic_router.get("/asset/{asset_id}", response_model=AssetOut)
async def get_asset_by_id(asset_id: int, db: AsyncSession = Depends(get_db)):
    a = await get_asset(db, asset_id)
    if not a:
        raise HTTPException(404, "Asset not found")
    return AssetOut.model_validate(a)

@basic_router.get("/vendors", response_model=List[VendorOut])
async def get_vendors(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    vs = await list_vendors(db, skip, limit)
    return [VendorOut.model_validate(v) for v in vs]

@basic_router.get("/vendor/{vendor_id}", response_model=VendorOut)
async def get_vendor_by_id(vendor_id: int, db: AsyncSession = Depends(get_db)):
    v = await get_vendor(db, vendor_id)
    if not v:
        raise HTTPException(404, "Vendor not found")
    return VendorOut.model_validate(v)

@basic_router.get("/sites", response_model=List[SiteOut])
async def get_sites(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    ss = await list_sites(db, skip, limit)
    return [SiteOut.model_validate(s) for s in ss]

@basic_router.get("/site/{site_id}", response_model=SiteOut)
async def get_site_by_id(site_id: int, db: AsyncSession = Depends(get_db)):
    s = await get_site(db, site_id)
    if not s:
        raise HTTPException(404, "Site not found")
    return SiteOut.model_validate(s)

@basic_router.get("/categories", response_model=List[TicketCategoryOut])
async def get_categories(db: AsyncSession = Depends(get_db)):
    cats = await list_categories(db)
    return [TicketCategoryOut.model_validate(c) for c in cats]

@basic_router.get("/statuses", response_model=List[TicketStatusOut])
async def get_statuses(db: AsyncSession = Depends(get_db)):
    st = await list_statuses(db)
    return [TicketStatusOut.model_validate(s) for s in st]

router.include_router(basic_router)

# Analytics sub-router
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])

@analytics_router.get("/status", response_model=List[StatusCount])
async def analytics_status(db: AsyncSession = Depends(get_db)):
    return await tickets_by_status(db)

@analytics_router.get("/open_by_site", response_model=List[SiteOpenCount])
async def analytics_open_by_site(db: AsyncSession = Depends(get_db)):
    return await open_tickets_by_site(db)

@analytics_router.get("/open_by_user", response_model=List[UserOpenCount])
async def analytics_open_by_user(db: AsyncSession = Depends(get_db)):
    return await open_tickets_by_user(db)

@analytics_router.get("/waiting_on_user", response_model=List[WaitingOnUserCount])
async def analytics_waiting_on_user(db: AsyncSession = Depends(get_db)):
    return await tickets_waiting_on_user(db)

@analytics_router.get("/sla_breaches")
async def analytics_sla_breaches(
    request: Request,
    sla_days: int = Query(2, ge=0),
    status_id: Optional[List[int]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = extract_filters(request, exclude=["sla_days", "status_id"])
    status_ids = status_id or None
    breaches = await sla_breaches(db, sla_days, filters=filters or None, status_ids=status_ids)
    return {"breaches": breaches}

router.include_router(analytics_router)

# AI sub-router
ai_router = APIRouter(prefix="/ai", tags=["ai"])

@ai_router.post("/suggest_response")
@limiter.limit("10/minute")
async def suggest_response(ticket: TicketOut, context: str = "") -> Dict[str, str]:
    resp = await ai_suggest_response(ticket.model_dump(), context)
    return {"response": resp}

@ai_router.post("/suggest_response/stream")
@limiter.limit("10/minute")
async def suggest_response_stream(ticket: TicketOut, context: str = "") -> StreamingResponse:
    async def gen() -> AsyncGenerator[str, None]:
        async for chunk in ai_stream_response(ticket.model_dump(), context):
            yield f"data: {chunk}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")

router.include_router(ai_router)

# Oncall endpoint
router.add_api_route(
    "/oncall",
    endpoint=lambda db=Depends(get_db): get_current_oncall(db),
    response_model=Optional[OnCallShiftOut],
    methods=["GET"],
    tags=["oncall"],
)

