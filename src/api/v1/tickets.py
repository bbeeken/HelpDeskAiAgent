from __future__ import annotations

import ast
import logging
import re
from typing import Any, List, Optional, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.models import VTicketMasterExpanded
from src.shared.schemas import (
    TicketCreate,
    TicketOut,
    TicketUpdate,
    TicketExpandedOut,
    TicketSearchOut,
    TicketSearchRequest,
)
from src.shared.schemas.search_params import TicketSearchParams
from src.shared.schemas.basic import TicketMessageOut
from src.shared.schemas.paginated import PaginatedResponse
from src.core.services.ticket_management import TicketManager, apply_semantic_filters

from .deps import get_db, get_db_with_commit, extract_filters

logger = logging.getLogger(__name__)

# ─── Tickets Router ───────────────────────────────────────────────────────────

# All ticket-related endpoints are registered under a single router. This
# simplifies route registration and ensures each endpoint exists only once.
ticket_router = APIRouter(prefix="/ticket", tags=["tickets"])


class MessageIn(BaseModel):
    message: str = Field(..., example="Thanks for the update")
    sender_code: str = Field(..., example="USR123")
    sender_name: Optional[str] = Field(None, example="John Doe")


class SearchBody(BaseModel):
    """Request body for JSON ticket search."""

    q: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=100)
    params: TicketSearchParams = Field(
        default_factory=TicketSearchParams,
        description="Optional search filters including created_after/before",
    )


async def create_ticket(db: AsyncSession, obj: Dict) -> Any:
    """Wrapper around TicketManager.create_ticket for easier testing."""
    return await TicketManager().create_ticket(db, obj)


def _extract_data_error_field(error: str) -> tuple[str, Any] | None:
    """Attempt to pull the offending column and value from a DB error message."""
    if not error:
        return None
    # Try to capture parameters dictionary from the error string
    params: Dict[str, Any] | None = None
    match_params = re.search(r"parameters:\s*({.*?})", error)
    if match_params:
        try:
            params = ast.literal_eval(match_params.group(1))
        except Exception:
            params = None
    # Look for explicit column mention first
    match_col = re.search(r'column "([^"]+)"', error)
    if match_col:
        col = match_col.group(1)
        if isinstance(params, dict) and col in params:
            return col, params[col]
        return col, None
    if isinstance(params, dict) and params:
        # Fallback to first parameter if no column found
        return next(iter(params.items()))
    return None


@ticket_router.get(
    "/search",
    response_model=List[TicketSearchOut],
    operation_id="search_tickets",
    response_model_by_alias=False,
)
async def search_tickets(
    q: str = Query(..., min_length=1),
    params: TicketSearchParams = Depends(),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[TicketSearchOut]:
    """Search tickets with optional date filtering."""
    logger.info("Searching tickets for '%s' (limit=%d)", q, limit)
    records, _ = await TicketManager().search_tickets(db, q, limit=limit, params=params)
    validated: List[TicketSearchOut] = []
    for r in records:
        data = {
            "Ticket_ID": r.Ticket_ID,
            "Subject": r.Subject,
            "body_preview": (r.Ticket_Body or "")[:200],
            "status_label": r.Ticket_Status_Label,
            "priority_level": r.Priority_Level,
        }
        try:
            validated.append(TicketSearchOut.model_validate(data))
        except ValidationError as exc:
            logger.error("Invalid search result %s: %s", getattr(r, "Ticket_ID", "?"), exc)
    return validated


@ticket_router.post(
    "/search",
    response_model=List[TicketSearchOut],
    operation_id="search_tickets_json",
)
async def search_tickets_json(
    payload: TicketSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> List[TicketSearchOut]:
    """POST variant of search_tickets supporting JSON body."""
    return await search_tickets(
        q=payload.q,
        params=payload.params or TicketSearchParams(),
        limit=payload.limit,
        db=db,
    )


@ticket_router.get(
    "",
    response_model=PaginatedResponse[TicketExpandedOut],
    operation_id="list_tickets",
    response_model_by_alias=False,
)
async def list_tickets(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    filters = extract_filters(request)
    sort = request.query_params.getlist("sort") or None
    items = await TicketManager().list_tickets(
        db,
        filters=filters or None,
        skip=skip,
        limit=limit,
        sort=sort,
    )
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






@ticket_router.get(
    "/expanded",
    response_model=PaginatedResponse[TicketExpandedOut],
    operation_id="list_expanded_tickets",
    response_model_by_alias=False,
)
async def list_tickets_expanded_alias(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    return await list_tickets(request, skip, limit, db)


@ticket_router.get(
    "/by_user",
    response_model=PaginatedResponse[TicketExpandedOut],
    operation_id="tickets_by_user",
    response_model_by_alias=False,
)
async def tickets_by_user_endpoint(
    request: Request,
    identifier: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    status: str | None = Query(
        None,
        description="Filter by ticket status. Allowed values: open, closed, resolved, in_progress, progress, waiting, pending.",
    ),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TicketExpandedOut]:
    filters = extract_filters(
        request, exclude=["identifier", "skip", "limit", "status"]
    )
    if status:
        try:
            apply_semantic_filters({"status": status})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=exc.args[0])
    items = await TicketManager().get_tickets_by_user(
        db,
        identifier,
        skip=skip,
        limit=limit,
        status=status,
        filters=filters or None,
    )
    total = len(
        await TicketManager().get_tickets_by_user(
            db,
            identifier,
            skip=0,
            limit=None,
            status=status,
            filters=filters or None,
        )
    )
    validated: List[TicketExpandedOut] = [TicketExpandedOut.model_validate(t) for t in items]
    return PaginatedResponse(items=validated, total=total, skip=skip, limit=limit)


@ticket_router.get(
    "/{ticket_id}",
    response_model=TicketExpandedOut,
    operation_id="get_ticket",
    response_model_by_alias=False,
)
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)) -> TicketExpandedOut:
    ticket = await TicketManager().get_ticket(db, ticket_id)
    if not ticket:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketExpandedOut.model_validate(ticket)


@ticket_router.post(
    "",
    response_model=TicketOut,
    status_code=201,
    operation_id="create_ticket",
)
async def create_ticket_endpoint(
    ticket: TicketCreate, db: AsyncSession = Depends(get_db_with_commit)
) -> TicketOut:
    payload = ticket.model_dump()
    result = await create_ticket(db, payload)
    if not result.success:
        field_val = _extract_data_error_field(result.error or "")
        if field_val:
            field, value = field_val
            logger.error(
                "Ticket creation failed for %s=%r: %s", field, value, result.error
            )
            raise HTTPException(
                status_code=503,
                detail=f"{result.error} (field {field}={value})",
            )
        logger.error("Ticket creation failed: %s", result.error)
        raise HTTPException(status_code=503, detail=result.error or "ticket create failed")
    return TicketOut.model_validate(result.data)


@ticket_router.post(
    "/json",
    response_model=TicketExpandedOut,
    status_code=201,
    operation_id="create_ticket_json",
    description="Create a ticket from JSON 📨",
    tags=["tickets", "📝"],
)
async def create_ticket_json(
    payload: TicketCreate = Body(...),
    db: AsyncSession = Depends(get_db_with_commit),
) -> TicketExpandedOut:
    data = payload.model_dump()
    result = await create_ticket(db, data)
    if not result.success:
        field_val = _extract_data_error_field(result.error or "")
        if field_val:
            field, value = field_val
            logger.error(
                "Ticket creation failed for %s=%r: %s", field, value, result.error
            )
            raise HTTPException(
                status_code=503,
                detail=f"{result.error} (field {field}={value})",
            )
        logger.error("Ticket creation failed: %s", result.error)
        raise HTTPException(status_code=503, detail=result.error or "ticket create failed")
    ticket = await TicketManager().get_ticket(db, result.data.Ticket_ID)
    return TicketExpandedOut.model_validate(ticket)


@ticket_router.put(
    "/{ticket_id}",
    response_model=TicketOut,
    operation_id="update_ticket",
)
async def update_ticket_endpoint(
    ticket_id: int,
    updates: TicketUpdate,
    db: AsyncSession = Depends(get_db_with_commit),
) -> TicketOut:
    updated = await TicketManager().update_ticket(
        db,
        ticket_id,
        updates.model_dump(exclude_unset=True),
        modified_by="Gil AI",
    )
    if not updated:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketOut.model_validate(updated)


@ticket_router.put(
    "/json/{ticket_id}",
    response_model=TicketExpandedOut,
    operation_id="update_ticket_json",
    description="Update a ticket with JSON ✏️",
    tags=["tickets", "📝"],
)
async def update_ticket_json(
    ticket_id: int,
    updates: TicketUpdate = Body(...),
    db: AsyncSession = Depends(get_db_with_commit),
) -> TicketExpandedOut:
    updated = await TicketManager().update_ticket(
        db, ticket_id, updates, modified_by="Gil AI"
    )
    if not updated:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket = await TicketManager().get_ticket(db, ticket_id)
    return TicketExpandedOut.model_validate(ticket)


@ticket_router.get(
    "/{ticket_id}/messages",
    response_model=List[TicketMessageOut],
    operation_id="list_ticket_messages",
    response_model_by_alias=False,
)
async def list_ticket_messages(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> List[TicketMessageOut]:
    ticket = await TicketManager().get_ticket(db, ticket_id)
    if not ticket:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    msgs = await TicketManager().get_messages(db, ticket_id)
    return [TicketMessageOut.model_validate(m) for m in msgs]


@ticket_router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageOut,
    operation_id="add_ticket_message",
)
async def add_ticket_message(
    ticket_id: int,
    msg: MessageIn,
    db: AsyncSession = Depends(get_db_with_commit),
) -> TicketMessageOut:
    ticket = await TicketManager().get_ticket(db, ticket_id)
    if not ticket:
        logger.warning("Ticket %s not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    created = await TicketManager().post_message(
        db, ticket_id, msg.message, msg.sender_code, sender_name=msg.sender_name
    )
    return TicketMessageOut.model_validate(created)


__all__ = ["ticket_router"]
