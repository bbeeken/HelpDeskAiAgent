from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import logging
from datetime import datetime, UTC

from db.mssql import SessionLocal
from db.models import Ticket, VTicketMasterExpanded

from tools.ticket_tools import (
    get_ticket_expanded,
    list_tickets_expanded,
    create_ticket,
    update_ticket,
    delete_ticket,
    search_tickets_expanded,
)

from tools.asset_tools import get_asset, list_assets
from tools.vendor_tools import get_vendor, list_vendors
from tools.attachment_tools import get_ticket_attachments
from tools.site_tools import get_site, list_sites
from tools.category_tools import list_categories
from tools.status_tools import list_statuses
from tools.message_tools import get_ticket_messages, post_ticket_message
from tools.analysis_tools import (
    tickets_by_status,
    open_tickets_by_site,
    sla_breaches,
    open_tickets_by_user,
    tickets_waiting_on_user,
)
from tools.oncall_tools import get_current_oncall
from tools.ai_tools import ai_suggest_response, ai_stream_response

from limiter import limiter

from schemas.ticket import TicketCreate, TicketOut, TicketUpdate, TicketExpandedOut
from schemas.oncall import OnCallShiftOut
from schemas.paginated import PaginatedResponse
from schemas.basic import (
    AssetOut,
    VendorOut,
    SiteOut,
    TicketCategoryOut,
    TicketStatusOut,
    TicketAttachmentOut,
    TicketMessageOut,
)
from schemas.analytics import StatusCount, SiteOpenCount, UserOpenCount, WaitingOnUserCount

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


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


@router.get("/ticket/{ticket_id}", response_model=TicketExpandedOut, response_model_by_alias=False)
async def api_get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)) -> TicketExpandedOut:
    ticket = await get_ticket_expanded(db, ticket_id)
    if not ticket:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/tickets", response_model=PaginatedResponse[TicketExpandedOut], response_model_by_alias=False)
async def api_list_tickets(
    request: Request,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    params = request.query_params
    filters = {k: v for k, v in params.items() if k not in {"skip", "limit", "sort"}}
    sort = params.getlist("sort") or None

    items = await list_tickets_expanded(db, skip, limit, filters=filters or None, sort=sort)

    count_query = select(func.count(VTicketMasterExpanded.Ticket_ID))
    for key, value in filters.items():
        if hasattr(VTicketMasterExpanded, key):
            count_query = count_query.filter(getattr(VTicketMasterExpanded, key) == value)
    total = await db.scalar(count_query) or 0

    ticket_out = []
    for t in items:
        try:
            ticket_out.append(TicketExpandedOut.model_validate(t))
        except Exception as e:
            logger.error("Invalid ticket %s: %s", getattr(t, "Ticket_ID", "?"), e)

    return PaginatedResponse[TicketExpandedOut](items=ticket_out, total=total, skip=skip, limit=limit)


@router.get("/tickets/expanded", response_model=PaginatedResponse[TicketExpandedOut], response_model_by_alias=False)
async def api_list_tickets_expanded(
    request: Request,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    params = request.query_params
    filters = {k: v for k, v in params.items() if k not in {"skip", "limit", "sort"}}
    sort = params.getlist("sort") or None

    items = await list_tickets_expanded(db, skip, limit, filters=filters or None, sort=sort)

    count_query = select(func.count(VTicketMasterExpanded.Ticket_ID))
    for key, value in filters.items():
        if hasattr(VTicketMasterExpanded, key):
            count_query = count_query.filter(getattr(VTicketMasterExpanded, key) == value)
    total = await db.scalar(count_query) or 0

    ticket_out = []
    for t in items:
        try:
            ticket_out.append(TicketExpandedOut.model_validate(t))
        except Exception as e:
            logger.error("Invalid ticket %s: %s", getattr(t, "Ticket_ID", "?"), e)

    return PaginatedResponse[TicketExpandedOut](items=ticket_out, total=total, skip=skip, limit=limit)


@router.get("/tickets/search", response_model=List[TicketExpandedOut], response_model_by_alias=False)
async def api_search_tickets(q: str, limit: int = 10, db: AsyncSession = Depends(get_db)) -> List[TicketExpandedOut]:
    logger.info("API search tickets query=%s limit=%s", q, limit)
    results = await search_tickets_expanded(db, q, limit)

    tickets = []
    for r in results:
        try:
            tickets.append(TicketExpandedOut.model_validate(r))
        except Exception as e:
            logger.error("Invalid ticket %s: %s", getattr(r, "Ticket_ID", "?"), e)

    return tickets


@router.post("/ticket", response_model=TicketOut)
async def api_create_ticket(ticket: TicketCreate, db: AsyncSession = Depends(get_db)) -> TicketOut:
    obj = Ticket(**ticket.model_dump(), Created_Date=datetime.now(UTC))
    logger.info("API create ticket")
    created = await create_ticket(db, obj)
    return created


@router.put("/ticket/{ticket_id}", response_model=TicketOut)
async def api_update_ticket(
    ticket_id: int, updates: TicketUpdate, db: AsyncSession = Depends(get_db)
) -> TicketOut:
    ticket = await update_ticket(db, ticket_id, updates)
    if not ticket:
        logger.warning("Ticket %s not found for update", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.delete("/ticket/{ticket_id}")
async def api_delete_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    if not await delete_ticket(db, ticket_id):
        logger.warning("Ticket %s not found for delete", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"deleted": True}


@router.get("/asset/{asset_id}", response_model=AssetOut)
async def api_get_asset(asset_id: int, db: AsyncSession = Depends(get_db)) -> AssetOut:
    asset = await get_asset(db, asset_id)
    if not asset:
        logger.warning("Asset %s not found", asset_id)
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetOut.model_validate(asset)


@router.get("/assets", response_model=List[AssetOut])
async def api_list_assets(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)) -> List[AssetOut]:
    assets = await list_assets(db, skip, limit)
    return [AssetOut.model_validate(a) for a in assets]


@router.get("/vendor/{vendor_id}", response_model=VendorOut)
async def api_get_vendor(vendor_id: int, db: AsyncSession = Depends(get_db)) -> VendorOut:
    vendor = await get_vendor(db, vendor_id)
    if not vendor:
        logger.warning("Vendor %s not found", vendor_id)
        raise HTTPException(status_code=404, detail="Vendor not found")
    return VendorOut.model_validate(vendor)


@router.get("/vendors", response_model=List[VendorOut])
async def api_list_vendors(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)) -> List[VendorOut]:
    vendors = await list_vendors(db, skip, limit)
    return [VendorOut.model_validate(v) for v in vendors]


@router.get("/site/{site_id}", response_model=SiteOut)
async def api_get_site(site_id: int, db: AsyncSession = Depends(get_db)) -> SiteOut:
    site = await get_site(db, site_id)
    if not site:
        logger.warning("Site %s not found", site_id)
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteOut.model_validate(site)


@router.get("/sites", response_model=List[SiteOut])
async def api_list_sites(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)) -> List[SiteOut]:
    sites = await list_sites(db, skip, limit)
    return [SiteOut.model_validate(s) for s in sites]


@router.get("/categories", response_model=List[TicketCategoryOut])
async def api_list_categories(db: AsyncSession = Depends(get_db)) -> List[TicketCategoryOut]:
    cats = await list_categories(db)
    return [TicketCategoryOut.model_validate(c) for c in cats]


@router.get("/statuses", response_model=List[TicketStatusOut])
async def api_list_statuses(db: AsyncSession = Depends(get_db)) -> List[TicketStatusOut]:
    statuses = await list_statuses(db)
    return [TicketStatusOut.model_validate(s) for s in statuses]


@router.get("/ticket/{ticket_id}/attachments", response_model=List[TicketAttachmentOut])
async def api_get_ticket_attachments(ticket_id: int, db: AsyncSession = Depends(get_db)) -> List[TicketAttachmentOut]:
    atts = await get_ticket_attachments(db, ticket_id)
    return [TicketAttachmentOut.model_validate(a) for a in atts]


@router.get("/ticket/{ticket_id}/messages", response_model=List[TicketMessageOut])
async def api_get_ticket_messages(ticket_
