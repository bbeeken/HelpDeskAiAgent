from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.ext.asyncio import AsyncSession

import logging

from db.mssql import SessionLocal

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
from tools.ai_tools import ai_suggest_response
from services.analytics_service import AnalyticsService
from limiter import limiter

from pydantic import BaseModel
from sqlalchemy import select, func

from schemas.ticket import (
    TicketCreate,
    TicketOut,
    TicketUpdate,
    TicketExpandedOut,
)

from schemas.oncall import OnCallShiftOut

from schemas.paginated import PaginatedResponse
from db.models import (
    Ticket,
    VTicketMasterExpanded,
)

from datetime import datetime, UTC

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:

        try:
            yield db
        finally:
            await db.close()

def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
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

@router.get(
    "/ticket/{ticket_id}",
    response_model=TicketExpandedOut,
    response_model_by_alias=False,
)
async def api_get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)) -> TicketExpandedOut:
    ticket = await get_ticket_expanded(db, ticket_id)
    if not ticket:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket

@router.get(
    "/tickets",
    response_model=PaginatedResponse[TicketExpandedOut],
    response_model_by_alias=False,
)

async def api_list_tickets(
    request: Request,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    params = request.query_params
    filters = {
        k: v
        for k, v in params.items()
        if k not in {"skip", "limit", "sort"}
    }
    sort = params.getlist("sort") or None

    items = await list_tickets_expanded(
        db, skip, limit, filters=filters or None, sort=sort
    )

    count_query = select(func.count(VTicketMasterExpanded.Ticket_ID))
    for key, value in filters.items():
        if hasattr(VTicketMasterExpanded, key):
            count_query = count_query.filter(
                getattr(VTicketMasterExpanded, key) == value
            )
    total = await db.scalar(count_query) or 0

    ticket_out = [TicketExpandedOut.from_orm(t) for t in items]
    return PaginatedResponse[TicketExpandedOut](items=ticket_out, total=total, skip=skip, limit=limit)
@router.get(
    "/tickets/expanded",
    response_model=PaginatedResponse[TicketExpandedOut],
    response_model_by_alias=False,
)
async def api_list_tickets_expanded(
    request: Request,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    params = request.query_params
    filters = {
        k: v
        for k, v in params.items()
        if k not in {"skip", "limit", "sort"}
    }
    sort = params.getlist("sort") or None

    items = await list_tickets_expanded(
        db, skip, limit, filters=filters or None, sort=sort
    )

    count_query = select(func.count(VTicketMasterExpanded.Ticket_ID))
    for key, value in filters.items():
        if hasattr(VTicketMasterExpanded, key):
            count_query = count_query.filter(
                getattr(VTicketMasterExpanded, key) == value
            )
    total = await db.scalar(count_query) or 0

    ticket_out = [TicketExpandedOut.from_orm(t) for t in items]
    return PaginatedResponse[TicketExpandedOut](
        items=ticket_out, total=total, skip=skip, limit=limit
    )

@router.get(
    "/tickets/search",
    response_model=List[TicketExpandedOut],
    response_model_by_alias=False,
)

async def api_search_tickets(
    q: str, limit: int = 10, db: AsyncSession = Depends(get_db)

) -> list[TicketExpandedOut]:

    logger.info("API search tickets query=%s limit=%s", q, limit)
    results = await search_tickets_expanded(db, q, limit)
    return [TicketExpandedOut.from_orm(r) for r in results]

@router.post("/ticket", response_model=TicketOut)
async def api_create_ticket(
    ticket: TicketCreate, db: AsyncSession = Depends(get_db)
) -> Ticket:
    obj = Ticket(**ticket.dict(), Created_Date=datetime.now(UTC))
    logger.info("API create ticket")
    created = await create_ticket(db, obj)
    return created

@router.put("/ticket/{ticket_id}", response_model=TicketOut)
async def api_update_ticket(
    ticket_id: int, updates: TicketUpdate, db: AsyncSession = Depends(get_db)
) -> Ticket:
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

@router.get("/asset/{asset_id}")
async def api_get_asset(asset_id: int, db: AsyncSession = Depends(get_db)) -> Any:

    asset = await get_asset(db, asset_id)
    if not asset:
        logger.warning("Asset %s not found", asset_id)
        raise HTTPException(status_code=404, detail="Asset not found")

    return asset

@router.get("/assets")
async def api_list_assets(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[Any]:
    return await list_assets(db, skip, limit)

@router.get("/vendor/{vendor_id}")
async def api_get_vendor(vendor_id: int, db: AsyncSession = Depends(get_db)) -> Any:

    vendor = await get_vendor(db, vendor_id)
    if not vendor:
        logger.warning("Vendor %s not found", vendor_id)
        raise HTTPException(status_code=404, detail="Vendor not found")

    return vendor

@router.get("/vendors")
async def api_list_vendors(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[Any]:
    return await list_vendors(db, skip, limit)

@router.get("/site/{site_id}")
async def api_get_site(site_id: int, db: AsyncSession = Depends(get_db)) -> Any:

    site = await get_site(db, site_id)
    if not site:
        logger.warning("Site %s not found", site_id)
        raise HTTPException(status_code=404, detail="Site not found")

    return site

@router.get("/sites")
async def api_list_sites(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[Any]:
    return await list_sites(db, skip, limit)

@router.get("/categories")
async def api_list_categories(db: AsyncSession = Depends(get_db)) -> list[Any]:
    return await list_categories(db)

@router.get("/statuses")
async def api_list_statuses(db: AsyncSession = Depends(get_db)) -> list[Any]:
    return await list_statuses(db)

@router.get("/ticket/{ticket_id}/attachments")
async def api_get_ticket_attachments(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> list[Any]:
    return await get_ticket_attachments(db, ticket_id)

@router.get("/ticket/{ticket_id}/messages")
async def api_get_ticket_messages(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> list[Any]:
    return await get_ticket_messages(db, ticket_id)

@router.post("/ticket/{ticket_id}/messages")
async def api_post_ticket_message(
    ticket_id: int,
    msg: MessageIn,
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await post_ticket_message(
        db, ticket_id, msg.message, msg.sender_code, msg.sender_name
    )

@router.post("/ai/suggest_response")
@limiter.limit("10/minute")
async def api_ai_suggest_response(
    request: Request, ticket: TicketOut, context: str = ""
) -> dict:

    return {"response": await ai_suggest_response(ticket.dict(), context)}

# Analysis endpoints

@router.get("/analytics/status")
async def api_tickets_by_status(
    db: AsyncSession = Depends(get_db),
) -> list[tuple[int | None, int]]:

    return await tickets_by_status(db)

@router.get("/analytics/open_by_site")
async def api_open_tickets_by_site(
    db: AsyncSession = Depends(get_db),
) -> list[tuple[int | None, int]]:

    return await open_tickets_by_site(db)

@router.get("/analytics/sla_breaches")
async def api_sla_breaches(
    sla_days: int = 2, db: AsyncSession = Depends(get_db)
) -> dict:
    return {"breaches": await sla_breaches(db, sla_days)}

@router.get("/analytics/open_by_user")
async def api_open_tickets_by_user(
    db: AsyncSession = Depends(get_db),
) -> list[tuple[str | None, int]]:

    return await open_tickets_by_user(db)

@router.get("/analytics/waiting_on_user")
async def api_tickets_waiting_on_user(
    db: AsyncSession = Depends(get_db),
) -> list[tuple[str | None, int]]:

    return await tickets_waiting_on_user(db)

@router.get("/oncall", response_model=OnCallShiftOut | None)
async def api_get_oncall(db: AsyncSession = Depends(get_db)) -> Any:
    return await get_current_oncall(db)
