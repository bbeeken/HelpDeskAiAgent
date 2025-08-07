import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.schemas.analytics import (
    StatusCount,
    SiteOpenCount,
    UserOpenCount,
    WaitingOnUserCount,
    TrendCount,
    StaffTicketReport,
)
from src.core.services.analytics_reporting import (
    tickets_by_status,
    open_tickets_by_site,
    open_tickets_by_user,
    get_staff_ticket_report,
    sla_breaches,
    tickets_waiting_on_user,
    ticket_trend,
)

from .deps import get_db, extract_filters

logger = logging.getLogger(__name__)

# ─── Analytics Sub-Router ─────────────────────────────────────────────────────

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics_router.get(
    "/status",
    response_model=List[StatusCount],
    operation_id="tickets_by_status",
)
async def tickets_by_status_endpoint(db: AsyncSession = Depends(get_db)) -> List[StatusCount]:
    result = await tickets_by_status(db)
    if not result.success:
        logger.error("tickets_by_status failed: %s", result.error)
        raise HTTPException(status_code=503, detail=result.error or "analytics failure")
    return result.data


@analytics_router.get(
    "/open_by_site",
    response_model=List[SiteOpenCount],
    operation_id="open_by_site",
)
async def open_by_site_endpoint(db: AsyncSession = Depends(get_db)) -> List[SiteOpenCount]:
    return await open_tickets_by_site(db)


@analytics_router.get(
    "/open_by_assigned_user",
    response_model=List[UserOpenCount],
    operation_id="open_by_assigned_user",
)
async def open_by_assigned_user_endpoint(
    request: Request, db: AsyncSession = Depends(get_db)
) -> List[UserOpenCount]:
    filters = extract_filters(request)
    return await open_tickets_by_user(db, filters or None)


@analytics_router.get(
    "/staff_report",
    response_model=StaffTicketReport,
    operation_id="staff_report",
)
async def staff_report_endpoint(
    assigned_email: str = Query(...),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StaffTicketReport:
    return await get_staff_ticket_report(
        db,
        assigned_email,
        start_date=start_date,
        end_date=end_date,
    )


@analytics_router.get(
    "/waiting_on_user",
    response_model=List[WaitingOnUserCount],
    operation_id="waiting_on_user",
)
async def waiting_on_user_endpoint(db: AsyncSession = Depends(get_db)) -> List[WaitingOnUserCount]:
    return await tickets_waiting_on_user(db)


@analytics_router.get(
    "/sla_breaches",
    operation_id="sla_breaches",
)
async def sla_breaches_endpoint(
    request: Request,
    sla_days: int = Query(2, ge=0),
    status_id: List[int] = Query(default_factory=list),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, int]:
    filters = extract_filters(request)
    breaches = await sla_breaches(
        db, sla_days, filters=filters or None, status_ids=status_id or None
    )
    return {"breaches": breaches}


@analytics_router.get(
    "/trend",
    response_model=List[TrendCount],
    operation_id="ticket_trend",
)
async def ticket_trend_endpoint(
    days: int = Query(7, ge=1),
    db: AsyncSession = Depends(get_db),
) -> List[TrendCount]:
    return await ticket_trend(db, days)


__all__ = ["analytics_router"]
