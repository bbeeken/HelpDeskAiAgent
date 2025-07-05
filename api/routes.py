# routers.py

import logging
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
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
from tools.attachment_tools import get_ticket_attachments
from tools.message_tools import get_ticket_messages, post_ticket_message
from tools.analysis_tools import (
    open_tickets_by_site,
    open_tickets_by_user,
    sla_breaches,
    tickets_by_status,
    tickets_waiting_on_user,
)
from tools.ai_tools import ai_stream_response, ai_suggest_response
from tools.oncall_tools import get_current_oncall
from tools.site_tools import get_site, list_sites
from tools.status_tools import list_statuses
from tools.category_tools import list_categories

# Schemas
from schemas.ticket import TicketCreate, TicketOut, TicketUpdate, TicketExpandedOut
from schemas.search import TicketSearchOut
from schemas.basic import (
    AssetOut,
    VendorOut,
    SiteOut,
    TicketAttachmentOut,
    TicketMessageOut,
    TicketStatusOut,
    TicketCategoryOut,
)
from schemas.oncall import OnCallShiftOut
from schemas.paginated import PaginatedResponse
from schemas.analytic import (
    SiteOpenCount,
    StatusCount,
    UserOpenCount,
    WaitingOnUserCount,
)

logger = logging.getLogger(__name__)

# ─── Database Dependency ──────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession and ensure it’s closed afterwards."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# ─── Helper Dependencies ──────────────────────────────────────────────────────

def extract_filters(
    request: Request, exclude: List[str] = ("skip", "limit", "sort", "sla_days", "status_id")
) -> Dict[str, Any]:
    return {
        key: value
        for key, value in request.query_params.multi_items()
        if key not in exclude
    }

def pagination_params(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, int]:
    return {"skip": skip, "limit": limit}

# ─── Main Router & Sub-Routers ─────────────────────────────────────────────────

router = APIRouter()

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

@ticket_router.post("", response_model=TicketOut)
async def create_ticket_endpoint(data: TicketCreate, db: AsyncSession = Depends(get_db)) -> TicketOut:
    payload = data.model_copy()
    payload["Created_Date"] = datetime.now(timezone.utc)
    created = await create_ticket(db, payload)
    return TicketOut.model_validate(created)

@ticket_router.put("/{ticket_id}", response_model=TicketOut)
async def update_ticket_endpoint(
    ticket_id: int,
    updates: TicketUpdate,
    db: AsyncSession = Depends(get_db)
) -> TicketOut:
    updated = await update_ticket(db, ticket_id, updates.model_dump(exclude_unset=True))
    if not updated:
        logger.warning("Failed to update ticket %s", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found or no changes applied")
    return TicketOut.model_validate(updated)

@ticket_router.delete("/{ticket_id}", status_code=204)
async def delete_ticket_endpoint(ticket_id: int, db: AsyncSession = Depends(get_db)):
    success = await delete_ticket(db, ticket_id)
    if not success:
        logger.warning("Failed to delete ticket %s", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return

@ticket_router.get("/{ticket_id}/messages", response_model=List[TicketMessageOut])
async def list_ticket_messages(ticket_id: int, db: AsyncSession = Depends(get_db)) -> List[TicketMessageOut]:
    msgs = await get_ticket_messages(db, ticket_id)
    return [TicketMessageOut.model_validate(m) for m in msgs]

@ticket_router.post("/{ticket_id}/messages", response_model=TicketMessageOut)
async def add_ticket_message(ticket_id: int, msg: MessageIn, db: AsyncSession = Depends(get_db)) -> TicketMessageOut:
    created = await post_ticket_message(db, ticket_id, msg.message, msg.sender_code, msg.sender_name)
    return TicketMessageOut.model_validate(created)

@ticket_router.get("/search", response_model=List[TicketSearchOut])
async def search_tickets(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[TicketSearchOut]:
    results = await search_tickets_expanded(db, q, limit)
    tickets: List[TicketSearchOut] = []
    for r in results:
        try:
            tickets.append(TicketSearchOut.model_validate(r))
        except Exception as e:
            logger.error("Invalid search ticket %s: %s", r.get("Ticket_ID", "?"), e)
    return tickets

router.include_router(ticket_router)

# ─── Lookup Sub-Router ────────────────────────────────────────────────────────

lookup_router = APIRouter(prefix="/lookup", tags=["lookup"])

@lookup_router.get("/assets", response_model=List[AssetOut])
async def list_assets_endpoint(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    assets = await list_assets(db, skip, limit)
    return [AssetOut.model_validate(a) for a in assets]

@lookup_router.get("/asset/{asset_id}", response_model=AssetOut)
async def get_asset_endpoint(asset_id: int, db: AsyncSession = Depends(get_db)):
    a = await get_asset(db, asset_id)
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetOut.model_validate(a)

@lookup_router.get("/vendors", response_model=List[VendorOut])
async def list_vendors_endpoint(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    vs = await list_vendors(db, skip, limit)
    return [VendorOut.model_validate(v) for v in vs]

@lookup_router.get("/vendor/{vendor_id}", response_model=VendorOut)
async def get_vendor_endpoint(vendor_id: int, db: AsyncSession = Depends(get_db)):
    v = await get_vendor(db, vendor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return VendorOut.model_validate(v)

@lookup_router.get("/sites", response_model=List[SiteOut])
async def list_sites_endpoint(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    ss = await list_sites(db, skip, limit)
    return [SiteOut.model_validate(s) for s in ss]

@lookup_router.get("/site/{site_id}", response_model=SiteOut)
async def get_site_endpoint(site_id: int, db: AsyncSession = Depends(get_db)):
    s = await get_site(db, site_id)
    if not s:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteOut.model_validate(s)

@lookup_router.get("/categories", response_model=List[TicketCategoryOut])
async def list_categories_endpoint(db: AsyncSession = Depends(get_db)):
    cats = await list_categories(db)
    return [TicketCategoryOut.model_validate(c) for c in cats]

@lookup_router.get("/statuses", response_model=List[TicketStatusOut])
async def list_statuses_endpoint(db: AsyncSession = Depends(get_db)):
    st = await list_statuses(db)
    return [TicketStatusOut.model_validate(s) for s in st]

@lookup_router.get("/ticket/{ticket_id}/attachments", response_model=List[TicketAttachmentOut])
async def api_get_ticket_attachments(ticket_id: int, db: AsyncSession = Depends(get_db)) -> List[TicketAttachmentOut]:
    atts = await get_ticket_attachments(db, ticket_id)
    return [TicketAttachmentOut.model_validate(a) for a in atts]

router.include_router(lookup_router)

# ─── Analytics Sub-Router ─────────────────────────────────────────────────────

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
):
    filters = extract_filters(request)
    breaches = await sla_breaches(
        db,
        sla_days,
        filters=filters or None,
        status_ids=status_id or None,
    )
    return {"breaches": breaches}

router.include_router(analytics_router)

# ─── AI Sub-Router ─────────────────────────────────────────────────────────────

ai_router = APIRouter(prefix="/ai", tags=["ai"])

@ai_router.post("/suggest_response", response_model=dict)
@limiter.limit("10/minute")
async def api_ai_suggest_response_route(ticket: dict) -> dict:
    try:
        result = await ai_suggest_response(ticket)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result

@ai_router.post("/suggest_response/stream")
@limiter.limit("10/minute")
async def api_ai_suggest_response_stream(ticket: dict) -> StreamingResponse:
    # validate input first
    try:
        TicketOut.model_validate(ticket)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def _generate() -> AsyncGenerator[str, None]:
        async for chunk in ai_stream_response(ticket):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")

router.include_router(ai_router)

# ─── On-Call Endpoint ──────────────────────────────────────────────────────────

@router.get("/oncall", response_model=Optional[OnCallShiftOut], tags=["oncall"])
async def api_get_current_oncall(db: AsyncSession = Depends(get_db)) -> Optional[OnCallShiftOut]:
    shift = await get_current_oncall(db)
    if not shift:
        raise HTTPException(status_code=404, detail="On-call shift not found")
    return OnCallShiftOut.model_validate(shift)

# ─── Application Factory ──────────────────────────────────────────────────────

def register_routes(app: FastAPI) -> None:
    """Include all routers on the FastAPI app."""
    app.include_router(router)
