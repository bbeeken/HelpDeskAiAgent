from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

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
from tools.ai_tools import ai_suggest_response, ai_stream_response
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

from schemas.basic import (
    AssetOut,
    VendorOut,
    SiteOut,
    TicketCategoryOut,
    TicketStatusOut,
    TicketAttachmentOut,
    TicketMessageOut,
)


from schemas.analytics import (
    StatusCount,
    SiteOpenCount,
    UserOpenCount,
    WaitingOnUserCount,
)

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
    """Retrieve a single ticket with related details.

    Parameters
    ----------
    ticket_id : int
        Identifier of the ticket to fetch.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    TicketExpandedOut
        Ticket record including joined labels and fields.
    """
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
    """List tickets with optional query filters and pagination.

    Parameters
    ----------
    request : Request
        Incoming request containing query parameters for filtering and sorting.
    skip : int, optional
        Number of records to skip from the start.
    limit : int, optional
        Maximum number of tickets to return.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    PaginatedResponse[TicketExpandedOut]
        Paginated ticket results.
    """
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

    ticket_out: list[TicketExpandedOut] = []
    for t in items:
        try:
            ticket_out.append(TicketExpandedOut.model_validate(t))
        except Exception as e:
            logger.error("Invalid ticket %s: %s", getattr(t, "Ticket_ID", "?"), e)
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
    """Return expanded ticket information with pagination.

    Parameters
    ----------
    request : Request
        Request containing filter and sort query parameters.
    skip : int, optional
        Number of records to offset the query by.
    limit : int, optional
        Maximum number of results to return.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    PaginatedResponse[TicketExpandedOut]
        Paginated expanded ticket data.
    """
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

    ticket_out: list[TicketExpandedOut] = []
    for t in items:
        try:
            ticket_out.append(TicketExpandedOut.model_validate(t))
        except Exception as e:
            logger.error("Invalid ticket %s: %s", getattr(t, "Ticket_ID", "?"), e)
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
    """Search tickets by text and return expanded results.

    Parameters
    ----------
    q : str
        Text to search for in ticket subjects or bodies.
    limit : int, optional
        Maximum number of matches to return.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[TicketExpandedOut]
        Matching tickets in expanded form.
    """

    logger.info("API search tickets query=%s limit=%s", q, limit)
    results = await search_tickets_expanded(db, q, limit)
    return [TicketExpandedOut.model_validate(r) for r in results]

@router.post("/ticket", response_model=TicketOut)
async def api_create_ticket(
    ticket: TicketCreate, db: AsyncSession = Depends(get_db)
) -> Ticket:
    """Create a new ticket entry.

    Parameters
    ----------
    ticket : TicketCreate
        Ticket details used to create the record.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    TicketOut
        The created ticket.
    """
    obj = Ticket(**ticket.model_dump(), Created_Date=datetime.now(UTC))
    logger.info("API create ticket")
    created = await create_ticket(db, obj)
    return created

@router.put("/ticket/{ticket_id}", response_model=TicketOut)
async def api_update_ticket(
    ticket_id: int, updates: TicketUpdate, db: AsyncSession = Depends(get_db)
) -> Ticket:
    """Update an existing ticket.

    Parameters
    ----------
    ticket_id : int
        Identifier of the ticket to update.
    updates : TicketUpdate
        Fields to modify on the ticket.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    TicketOut
        The updated ticket record or 404 if not found.
    """
    ticket = await update_ticket(db, ticket_id, updates)
    if not ticket:
        logger.warning("Ticket %s not found for update", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket

@router.delete("/ticket/{ticket_id}")
async def api_delete_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Delete a ticket by ID.

    Parameters
    ----------
    ticket_id : int
        Identifier of the ticket to remove.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    dict
        ``{"deleted": True}`` when the ticket is removed.
    """
    if not await delete_ticket(db, ticket_id):

        logger.warning("Ticket %s not found for delete", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {"deleted": True}

@router.get("/asset/{asset_id}", response_model=AssetOut)
async def api_get_asset(asset_id: int, db: AsyncSession = Depends(get_db)) -> AssetOut:
    """Fetch a single asset by its identifier.

    Parameters
    ----------
    asset_id : int
        Identifier of the asset to retrieve.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    AssetOut
        Asset information.
    """

    asset = await get_asset(db, asset_id)
    if not asset:
        logger.warning("Asset %s not found", asset_id)
        raise HTTPException(status_code=404, detail="Asset not found")

    return AssetOut.model_validate(asset)

@router.get("/assets", response_model=List[AssetOut])
async def api_list_assets(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[AssetOut]:
    """Return a list of assets.

    Parameters
    ----------
    skip : int, optional
        Offset into the asset list.
    limit : int, optional
        Maximum number of assets to return.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[AssetOut]
        Requested slice of assets.
    """
    assets = await list_assets(db, skip, limit)
    return [AssetOut.model_validate(a) for a in assets]

@router.get("/vendor/{vendor_id}", response_model=VendorOut)
async def api_get_vendor(vendor_id: int, db: AsyncSession = Depends(get_db)) -> VendorOut:
    """Retrieve a vendor record by ID.

    Parameters
    ----------
    vendor_id : int
        Identifier of the vendor to fetch.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    VendorOut
        The vendor information.
    """

    vendor = await get_vendor(db, vendor_id)
    if not vendor:
        logger.warning("Vendor %s not found", vendor_id)
        raise HTTPException(status_code=404, detail="Vendor not found")

    return VendorOut.model_validate(vendor)

@router.get("/vendors", response_model=List[VendorOut])
async def api_list_vendors(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[VendorOut]:
    """List vendors with pagination.

    Parameters
    ----------
    skip : int, optional
        Offset into the vendor list.
    limit : int, optional
        Maximum number of vendors to return.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[VendorOut]
        Requested slice of vendors.
    """
    vendors = await list_vendors(db, skip, limit)
    return [VendorOut.model_validate(v) for v in vendors]

@router.get("/site/{site_id}", response_model=SiteOut)
async def api_get_site(site_id: int, db: AsyncSession = Depends(get_db)) -> SiteOut:
    """Retrieve a site by ID.

    Parameters
    ----------
    site_id : int
        Identifier of the site to fetch.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    SiteOut
        The site information.
    """

    site = await get_site(db, site_id)
    if not site:
        logger.warning("Site %s not found", site_id)
        raise HTTPException(status_code=404, detail="Site not found")

    return SiteOut.model_validate(site)

@router.get("/sites", response_model=List[SiteOut])
async def api_list_sites(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[SiteOut]:
    """Return a paginated list of sites.

    Parameters
    ----------
    skip : int, optional
        Offset into the site list.
    limit : int, optional
        Maximum number of sites to return.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[SiteOut]
        Requested slice of sites.
    """
    sites = await list_sites(db, skip, limit)
    return [SiteOut.model_validate(s) for s in sites]

@router.get("/categories", response_model=List[TicketCategoryOut])
async def api_list_categories(db: AsyncSession = Depends(get_db)) -> list[TicketCategoryOut]:
    """List available ticket categories.

    Parameters
    ----------
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[TicketCategoryOut]
        Ticket categories ordered by ID.
    """
    cats = await list_categories(db)
    return [TicketCategoryOut.model_validate(c) for c in cats]

@router.get("/statuses", response_model=List[TicketStatusOut])
async def api_list_statuses(db: AsyncSession = Depends(get_db)) -> list[TicketStatusOut]:
    """Return all ticket status values.

    Parameters
    ----------
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[TicketStatusOut]
        Available ticket statuses.
    """
    statuses = await list_statuses(db)
    return [TicketStatusOut.model_validate(s) for s in statuses]

@router.get("/ticket/{ticket_id}/attachments", response_model=List[TicketAttachmentOut])
async def api_get_ticket_attachments(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> list[TicketAttachmentOut]:
    """Return attachments for a given ticket.

    Parameters
    ----------
    ticket_id : int
        Ticket identifier whose attachments should be listed.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[TicketAttachmentOut]
        Attachment metadata for the ticket.
    """
    atts = await get_ticket_attachments(db, ticket_id)
    return [TicketAttachmentOut.model_validate(a) for a in atts]

@router.get("/ticket/{ticket_id}/messages", response_model=List[TicketMessageOut])
async def api_get_ticket_messages(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> list[TicketMessageOut]:
    """List messages associated with a ticket.

    Parameters
    ----------
    ticket_id : int
        Identifier of the ticket.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[TicketMessageOut]
        Messages sorted by timestamp.
    """
    msgs = await get_ticket_messages(db, ticket_id)
    return [TicketMessageOut.model_validate(m) for m in msgs]

@router.post("/ticket/{ticket_id}/messages", response_model=TicketMessageOut)
async def api_post_ticket_message(
    ticket_id: int,
    msg: MessageIn,
    db: AsyncSession = Depends(get_db),
) -> TicketMessageOut:
    """Post a message to a ticket.

    Parameters
    ----------
    ticket_id : int
        Identifier of the ticket.
    msg : MessageIn
        Message body and sender details.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    TicketMessageOut
        The saved message record.
    """
    created = await post_ticket_message(
        db, ticket_id, msg.message, msg.sender_code, msg.sender_name
    )
    return TicketMessageOut.model_validate(created)

@router.post("/ai/suggest_response")
@limiter.limit("10/minute")
async def api_ai_suggest_response(
    request: Request, ticket: TicketOut, context: str = ""
) -> dict:
    """Return an AI-generated reply suggestion for a ticket.

    Parameters
    ----------
    request : Request
        FastAPI request object used for rate limiting.
    ticket : TicketOut
        Ticket data to base the suggestion on.
    context : str, optional
        Additional conversation context.

    Returns
    -------
    dict
        ``{"response": str}`` containing the suggested reply text.
    """

    return {"response": await ai_suggest_response(ticket.model_dump(), context)}


@router.post("/ai/suggest_response/stream")
@limiter.limit("10/minute")
async def api_ai_suggest_response_stream(
    request: Request, ticket: TicketOut, context: str = ""
) -> StreamingResponse:
    """Stream an AI-generated reply suggestion for a ticket.

    Parameters
    ----------
    request : Request
        FastAPI request object used for rate limiting.
    ticket : TicketOut
        Ticket data used to generate suggestions.
    context : str, optional
        Additional conversation context.

    Returns
    -------
    StreamingResponse
        Server-sent events stream with response chunks.
    """

    async def _generate() -> AsyncGenerator[str, None]:
        async for chunk in ai_stream_response(ticket.model_dump(), context):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")

# Analysis endpoints

@router.get("/analytics/status", response_model=list[StatusCount])
async def api_tickets_by_status(
    db: AsyncSession = Depends(get_db),
) -> list[StatusCount]:
    """Count tickets grouped by status.

    Parameters
    ----------
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[StatusCount]
        Aggregated counts per status value.
    """

    return await tickets_by_status(db)

@router.get("/analytics/open_by_site", response_model=list[SiteOpenCount])
async def api_open_tickets_by_site(
    db: AsyncSession = Depends(get_db),
) -> list[SiteOpenCount]:
    """Summarize open tickets per site.

    Parameters
    ----------
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[SiteOpenCount]
        Count of open tickets for each site.
    """

    return await open_tickets_by_site(db)

@router.get("/analytics/sla_breaches")
async def api_sla_breaches(
    request: Request,
    sla_days: int = 2,
    status_id: list[int] | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:


    """Count tickets older than the SLA threshold.

    Parameters
    ----------
    sla_days : int, optional
        Age in days to consider a ticket in breach.
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    dict
        ``{"breaches": int}`` with the number of tickets exceeding the SLA.
    """
    return {"breaches": await sla_breaches(db, sla_days)}


@router.get("/analytics/open_by_user", response_model=list[UserOpenCount])
async def api_open_tickets_by_user(
    db: AsyncSession = Depends(get_db),

) -> list[tuple[str | None, int]]:
    """List open ticket counts grouped by assigned user.

    Parameters
    ----------
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[tuple[str | None, int]]
        Tuples of user email and open ticket count.
    """


    return await open_tickets_by_user(db)

@router.get("/analytics/waiting_on_user", response_model=list[WaitingOnUserCount])
async def api_tickets_waiting_on_user(
    db: AsyncSession = Depends(get_db),

) -> list[tuple[str | None, int]]:
    """Count tickets waiting for user response.

    Parameters
    ----------
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    list[tuple[str | None, int]]
        Tuples of contact email and waiting ticket count.
    """


    return await tickets_waiting_on_user(db)

@router.get("/oncall", response_model=OnCallShiftOut | None)
async def api_get_oncall(db: AsyncSession = Depends(get_db)) -> Any:
    """Return the current on-call shift if available.

    Parameters
    ----------
    db : AsyncSession
        Database session dependency.

    Returns
    -------
    OnCallShiftOut | None
        Details of the active on-call user or ``None`` when no shift is active.
    """
    return await get_current_oncall(db)
