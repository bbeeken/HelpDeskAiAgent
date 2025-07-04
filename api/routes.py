import logging
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.mssql import SessionLocal
from db.models import VTicketMasterExpanded

from limiter import limiter

# Tools
from tools.ticket_tools import (
    create_ticket,
    update_ticket,
    delete_ticket,
    get_ticket_expanded,
    list_tickets_expanded,
    search_tickets_expanded,
)
from tools.asset_tools import get_asset, list_assets
from tools.vendor_tools import get_vendor, list_vendors
from tools.site_tools import get_site, list_sites
from tools.category_tools import list_categories
from tools.status_tools import list_statuses
from tools.attachment_tools import get_ticket_attachments
from tools.message_tools import get_ticket_messages, post_ticket_message
from tools.analysis_tools import (
    tickets_by_status,
    open_tickets_by_site,
    open_tickets_by_user,
    sla_breaches,
    tickets_waiting_on_user,
    ticket_trend,
)
from tools.ai_tools import ai_suggest_response, ai_stream_response
from tools.oncall_tools import get_current_oncall

# Schemas
from schemas.ticket import (
    TicketCreate,
    TicketOut,
    TicketUpdate,
    TicketExpandedOut,
    TicketSearchOut,
)
from schemas.basic import (
    AssetOut,
    VendorOut,
    SiteOut,
    TicketCategoryOut,
    TicketStatusOut,
    TicketAttachmentOut,
    TicketMessageOut,
)
from schemas.analytics import StatusCount, SiteOpenCount, UserOpenCount, WaitingOnUserCount, TrendCount
from schemas.oncall import OnCallShiftOut
from schemas.paginated import PaginatedResponse

logger = logging.getLogger(__name__)

# ─── Database Dependency ──────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a SQLAlchemy AsyncSession, ensuring proper cleanup.
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# ─── Utility ──────────────────────────────────────────────────────────────────
def extract_filters(
    request: Request,
    exclude: List[str] = ("skip", "limit", "sort", "sla_days", "status_id")
) -> Dict[str, Any]:
    """
    Extract arbitrary query parameters for filtering, excluding reserved keys.
    """
    return {
        key: value
        for key, value in request.query_params.multi_items()
        if key not in exclude
    }

# ─── Tickets Sub-Router ───────────────────────────────────────────────────────
ticket_router = APIRouter(prefix="/ticket", tags=["tickets"])

class MessageIn(BaseModel):
    message: str = Field(..., example="Thanks for the update")
    sender_code: str = Field(..., example="USR123")
    sender_name: str = Field(..., example="John Doe")

@ticket_router.get("/{ticket_id}", response_model=TicketExpandedOut)
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)) -> TicketExpandedOut:
    ticket = await get_ticket_expanded(db, ticket_id)
    if not ticket:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketExpandedOut.model_validate(ticket)

@ticket_router.get("", response_model=PaginatedResponse[TicketExpandedOut])
async def list_tickets(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    filters = extract_filters(request)
    sort = request.query_params.getlist("sort") or None
    items = await list_tickets_expanded(db, skip, limit, filters=filters or None, sort=sort)
    count_q = select(func.count(VTicketMasterExpanded.Ticket_ID))
    for k, v in filters.items():
        if hasattr(VTicketMasterExpanded, k):
            count_q = count_q.filter(getattr(VTicketMasterExpanded, k) == v)
    total = await db.scalar(count_q) or 0

    validated: List[TicketExpandedOut] = []
    for t in items:
        try:
            validated.append(TicketExpandedOut.model_validate(t))
        except ValidationError as exc:
            logger.error("Invalid ticket %s: %s", getattr(t, "Ticket_ID", "?"), exc)

    return PaginatedResponse(items=validated, total=total, skip=skip, limit=limit)

@ticket_router.get("/search", response_model=List[TicketSearchOut])
async def search_tickets(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[TicketSearchOut]:
    logger.info("Searching tickets for '%s' (limit=%d)", q, limit)
    results = await search_tickets_expanded(db, q, limit)
    validated: List[TicketSearchOut] = []
    for r in results:
        try:
            validated.append(TicketSearchOut.model_validate(r))
        except ValidationError as exc:
            logger.error("Invalid search result %s: %s", r.get("Ticket_ID", "?"), exc)
    return validated

@ticket_router.post("", response_model=TicketOut, status_code=201)
async def create_ticket_endpoint(
    ticket: TicketCreate, db: AsyncSession = Depends(get_db)
) -> TicketOut:
    payload = ticket.model_dump()
    payload["Created_Date"] = datetime.now(timezone.utc)
    created = await create_ticket(db, payload)
    return TicketOut.model_validate(created)

@ticket_router.put("/{ticket_id}", response_model=TicketOut)
async def update_ticket_endpoint(
    ticket_id: int,
    updates: TicketUpdate,
    db: AsyncSession = Depends(get_db),
) -> TicketOut:
    updated = await update_ticket(db, ticket_id, updates.model_dump(exclude_unset=True))
    if not updated:
        logger.warning("Ticket %s not found or no changes applied", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found or no changes")
    return TicketOut.model_validate(updated)

@ticket_router.delete("/{ticket_id}", status_code=204)
async def delete_ticket_endpoint(ticket_id: int, db: AsyncSession = Depends(get_db)):
    success = await delete_ticket(db, ticket_id)
    if not success:
        logger.warning("Ticket %s not found for deletion", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")

@ticket_router.get("/{ticket_id}/messages", response_model=List[TicketMessageOut])
async def list_ticket_messages(ticket_id: int, db: AsyncSession = Depends(get_db)) -> List[TicketMessageOut]:
    msgs = await get_ticket_messages(db, ticket_id)
    return [TicketMessageOut.model_validate(m) for m in msgs]

@ticket_router.post("/{ticket_id}/messages", response_model=TicketMessageOut)
async def add_ticket_message(
    ticket_id: int,
    msg: MessageIn,
    db: AsyncSession = Depends(get_db),
) -> TicketMessageOut:
    created = await post_ticket_message(db, ticket_id, msg.message, msg.sender_code, msg.sender_name)
    return TicketMessageOut.model_validate(created)

# ─── Lookup Sub-Router ────────────────────────────────────────────────────────
lookup_router = APIRouter(prefix="/lookup", tags=["lookup"])

@lookup_router.get("/assets", response_model=List[AssetOut])
async def list_assets_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
) -> List[AssetOut]:
    assets = await list_assets(db, skip, limit)
    return [AssetOut.model_validate(a) for a in assets]

@lookup_router.get("/asset/{asset_id}", response_model=AssetOut)
async def get_asset_endpoint(asset_id: int, db: AsyncSession = Depends(get_db)) -> AssetOut:
    a = await get_asset(db, asset_id)
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetOut.model_validate(a)

@lookup_router.get("/vendors", response_model=List[VendorOut])
async def list_vendors_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
) -> List[VendorOut]:
    vs = await list_vendors(db, skip, limit)
    return [VendorOut.model_validate(v) for v in vs]

@lookup_router.get("/vendor/{vendor_id}", response_model=VendorOut)
async def get_vendor_endpoint(vendor_id: int, db: AsyncSession = Depends(get_db)) -> VendorOut:
    v = await get_vendor(db, vendor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return VendorOut.model_validate(v)

@lookup_router.get("/sites", response_model=List[SiteOut])
async def list_sites_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
) -> List[SiteOut]:
    ss = await list_sites(db, skip, limit)
    return [SiteOut.model_validate(s) for s in ss]

@lookup_router.get("/site/{site_id}", response_model=SiteOut)
async def get_site_endpoint(site_id: int, db: AsyncSession = Depends(get_db)) -> SiteOut:
    s = await get_site(db, site_id)
    if not s:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteOut.model_validate(s)

@lookup_router.get("/categories", response_model=List[TicketCategoryOut])
async def list_categories_endpoint(db: AsyncSession = Depends(get_db)) -> List[TicketCategoryOut]:
    cats = await list_categories(db)
    return [TicketCategoryOut.model_validate(c) for c in cats]

@lookup_router.get("/statuses", response_model=List[TicketStatusOut])
async def list_statuses_endpoint(db: AsyncSession = Depends(get_db)) -> List[TicketStatusOut]:
    stats = await list_statuses(db)
    return [TicketStatusOut.model_validate(s) for s in stats]

@lookup_router.get("/ticket/{ticket_id}/attachments", response_model=List[TicketAttachmentOut])
async def get_ticket_attachments_endpoint(ticket_id: int, db: AsyncSession = Depends(get_db)) -> List[TicketAttachmentOut]:
    atts = await get_ticket_attachments(db, ticket_id)
    return [TicketAttachmentOut.model_validate(a) for a in atts]

# ─── Analytics Sub-Router ────────────────────────────────────────────────────
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])

@analytics_router.get("/status", response_model=List[StatusCount])
async def tickets_by_status_endpoint(db: AsyncSession = Depends(get_db)) -> List[StatusCount]:
    return await tickets_by_status(db)

@analytics_router.get("/open_by_site", response_model=List[SiteOpenCount])
async def open_by_site_endpoint(db: AsyncSession = Depends(get_db)) -> List[SiteOpenCount]:
    return await open_tickets_by_site(db)

@analytics_router.get("/open_by_user", response_model=List[UserOpenCount])
async def open_by_user_endpoint(db: AsyncSession = Depends(get_db)) -> List[UserOpenCount]:
    return await open_tickets_by_user(db)

@analytics_router.get("/waiting_on_user", response_model=List[WaitingOnUserCount])
async def waiting_on_user_endpoint(db: AsyncSession = Depends(get_db)) -> List[WaitingOnUserCount]:
    return await tickets_waiting_on_user(db)

@analytics_router.get("/sla_breaches")
async def sla_breaches_endpoint(
    request: Request,
    sla_days: int = Query(2, ge=0),
    status_id: Optional[List[int]] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, int]:
    filters = extract_filters(request)
    breaches = await sla_breaches(db, sla_days, filters=filters or None, status_ids=status_id or None)
    return {"breaches": breaches}

@analytics_router.get("/trend", response_model=List[TrendCount])
async def ticket_trend_endpoint(days: int = Query(7, ge=1), db: AsyncSession = Depends(get_db)) -> List[TrendCount]:
    return await ticket_trend(db, days)

# ─── AI Sub-Router ───────────────────────────────────────────────────────────
ai_router = APIRouter(prefix="/ai", tags=["ai"])

@ai_router.post("/suggest_response", response_model=Dict[str, str])
@limiter.limit("10/minute")
async def suggest_response(ticket: TicketOut) -> Dict[str, str]:
    try:
        return {"response": await ai_suggest_response(ticket.model_dump(), "")}
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@ai_router.post("/suggest_response/stream")
@limiter.limit("10/minute")
async def suggest_response_stream(ticket: TicketOut) -> StreamingResponse:
    ticket.model_validate(ticket.model_dump())
    async def _gen() -> AsyncGenerator[str, None]:
        async for chunk in ai_stream_response(ticket.model_dump(), ""):
            yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")

# ─── On-Call Sub-Router ───────────────────────────────────────────────────────
oncall_router = APIRouter(prefix="/oncall", tags=["oncall"])

@oncall_router.get("", response_model=Optional[OnCallShiftOut])
async def get_oncall_shift(db: AsyncSession = Depends(get_db)) -> Optional[OnCallShiftOut]:
    shift = await get_current_oncall(db)
    return OnCallShiftOut.model_validate(shift) if shift else None

# ─── Application Registration ─────────────────────────────────────────────────
def register_routes(app: FastAPI) -> None:
    app.include_router(ticket_router)
    app.include_router(lookup_router)
    app.include_router(analytics_router)
    app.include_router(ai_router)
    app.include_router(oncall_router)
