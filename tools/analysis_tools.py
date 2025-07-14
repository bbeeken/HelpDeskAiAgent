"""Analytics helpers for summarizing ticket data."""

import logging
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta, timezone, date as date_cls
from typing import Any, Dict, List, Optional
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from db.models import Ticket, TicketStatus, Site
from schemas.analytics import (
    StatusCount,
    SiteOpenCount,
    UserOpenCount,
    WaitingOnUserCount,
    TrendCount,
    StaffTicketReport,
)


logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    """Trend direction indicators."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class TrendAnalysis:
    direction: TrendDirection
    change_percentage: float
    velocity: float
    prediction_next_period: float
    confidence: float

    def to_llm_format(self) -> Dict[str, Any]:
        return {
            "trend": self.direction.value,
            "change": f"{self.change_percentage:+.1f}%",
            "momentum": "accelerating" if self.velocity > 0 else "decelerating",
            "forecast": {
                "next_value": self.prediction_next_period,
                "confidence": f"{self.confidence:.0%}",
            },
        }


_analytics_cache: dict[str, tuple[float, Any]] = {}
_cache_ttl = 300  # 5 minutes


async def tickets_by_status(
    db: AsyncSession,
) -> List[StatusCount]:
    """Return counts of tickets grouped by status with caching."""
    cache_key = "tickets_by_status"

    if cache_key in _analytics_cache:
        cached_time, result = _analytics_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            return result

    logger.info("Calculating tickets by status")
    result = await db.execute(
        select(
            Ticket.Ticket_Status_ID,
            TicketStatus.Label,
            func.count(Ticket.Ticket_ID),
        ).join(
            TicketStatus,
            Ticket.Ticket_Status_ID == TicketStatus.ID,
            isouter=True,
        ).group_by(
            Ticket.Ticket_Status_ID,
            TicketStatus.Label,
        )
    )
    status_counts = [
        StatusCount(status_id=row[0], status_label=row[1], count=row[2])
        for row in result.all()
    ]

    _analytics_cache[cache_key] = (time.time(), status_counts)
    return status_counts


async def open_tickets_by_site(
    db: AsyncSession,
) -> List[SiteOpenCount]:
    """Return open ticket counts grouped by site."""
    logger.info("Calculating open tickets by site")
    result = await db.execute(
        select(
            Ticket.Site_ID,
            Site.Label,
            func.count(Ticket.Ticket_ID),
        ).join(
            Site,
            Ticket.Site_ID == Site.ID,
            isouter=True,
        ).filter(
            Ticket.Ticket_Status_ID != 3  # assuming 3 is 'closed'
        ).group_by(
            Ticket.Site_ID,
            Site.Label,
        )
    )
    return [
        SiteOpenCount(site_id=row[0], site_label=row[1], count=row[2])
        for row in result.all()
    ]


async def sla_breaches(
    db: AsyncSession,
    sla_days: int = 2,
    filters: Optional[Dict[str, Any]] = None,
    status_ids: Optional[List[int] | int] = None,
) -> int:
    """Count tickets older than `sla_days` with optional filtering."""
    logger.info(
        "Counting SLA breaches older than %s days with filters=%s statuses=%s",
        sla_days,
        filters,
        status_ids,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=sla_days)
    query = select(func.count(Ticket.Ticket_ID)).filter(Ticket.Created_Date < cutoff)

    if status_ids is not None:
        if isinstance(status_ids, int):
            status_ids = [status_ids]
        query = query.filter(Ticket.Ticket_Status_ID.in_(status_ids))
    else:

        # Default to counting only open or in-progress tickets
        query = query.filter(Ticket.Ticket_Status_ID.in_([1, 2]))
        query = query.filter(Ticket.Ticket_Status_ID.in_([1, 2,4,5,6]))

    if filters:
        for key, value in filters.items():
            if hasattr(Ticket, key):
                query = query.filter(getattr(Ticket, key) == value)

    result = await db.execute(query)
    return result.scalar_one()


async def open_tickets_by_user(db: AsyncSession) -> List[UserOpenCount]:
    """Return open ticket counts grouped by assigned technician."""
    logger.info("Calculating open tickets by user")
    result = await db.execute(
        select(
            Ticket.Assigned_Email,
            func.count(Ticket.Ticket_ID),
        ).filter(
            Ticket.Ticket_Status_ID != 3
        ).group_by(
            Ticket.Assigned_Email
        )
    )
    return [
        UserOpenCount(assigned_email=row[0], count=row[1])
        for row in result.all()
    ]


async def tickets_waiting_on_user(db: AsyncSession) -> List[WaitingOnUserCount]:
    """Return counts of tickets awaiting user response (status == 4)."""
    logger.info("Calculating tickets waiting on user")
    result = await db.execute(
        select(
            Ticket.Ticket_Contact_Email,
            func.count(Ticket.Ticket_ID),
        ).filter(
            Ticket.Ticket_Status_ID == 4
        ).group_by(
            Ticket.Ticket_Contact_Email
        )
    )
    return [
        WaitingOnUserCount(contact_email=row[0], count=row[1])
        for row in result.all()
    ]


async def ticket_trend(db: AsyncSession, days: int = 7) -> List[TrendCount]:
    """Return ticket counts grouped by creation date over the past `days` days."""
    logger.info("Calculating ticket trend for the past %d days", days)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Ticket.Created_Date),
            func.count(Ticket.Ticket_ID),
        ).filter(
            Ticket.Created_Date >= start
        ).group_by(
            func.date(Ticket.Created_Date)
        ).order_by(
            func.date(Ticket.Created_Date)
        )
    )

    trend: List[TrendCount] = []
    for d, c in result.all():
        if isinstance(d, str):
            d = date_cls.fromisoformat(d)
        elif isinstance(d, datetime):
            d = d.date()
        trend.append(TrendCount(date=d, count=c))
    return trend


async def get_staff_ticket_report(
    db: AsyncSession,
    email: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> StaffTicketReport:
    """Return open/closed counts for a technician with recent tickets."""

    base_query = select(Ticket).filter(Ticket.Assigned_Email == email)
    if start_date:
        base_query = base_query.filter(Ticket.Created_Date >= start_date)
    if end_date:
        base_query = base_query.filter(Ticket.Created_Date <= end_date)

    open_q = base_query.filter(Ticket.Ticket_Status_ID != 3)
    closed_q = base_query.filter(Ticket.Ticket_Status_ID == 3)

    open_count = await db.scalar(select(func.count()).select_from(open_q.subquery())) or 0
    closed_count = await db.scalar(select(func.count()).select_from(closed_q.subquery())) or 0

    recent_q = (
        base_query.order_by(Ticket.Created_Date.desc()).with_only_columns(Ticket.Ticket_ID).limit(5)
    )
    result = await db.execute(recent_q)
    recent_ids = [row[0] for row in result.all()]

    return StaffTicketReport(
        assigned_email=email,
        open_count=open_count,
        closed_count=closed_count,
        recent_ticket_ids=recent_ids,
    )


class AnalyticsTools:
    """Enhanced analytics helper with trends, insights, and predictions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_comprehensive_dashboard(
        self, time_range_days: int = 30, include_predictions: bool = True
    ) -> Dict[str, Any]:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=time_range_days)

        metrics = await self._gather_all_metrics(start_date, end_date)
        trends = await self._analyze_trends(metrics, time_range_days)
        insights = self._generate_insights(metrics, trends)

        dashboard: Dict[str, Any] = {
            "overview": {
                "period": f"Last {time_range_days} days",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_tickets": metrics["total_tickets"],
                "active_tickets": metrics["active_tickets"],
                "resolution_rate": f"{metrics['resolution_rate']:.1%}",
            },
            "trends": {
                "ticket_volume": trends["volume_trend"].to_llm_format(),
            },
            "insights": insights,
        }
        if include_predictions:
            dashboard["predictions"] = await self._generate_predictions(metrics, trends)
        return dashboard

    async def _gather_all_metrics(
        self, start: datetime, end: datetime
    ) -> Dict[str, Any]:
        total = await self.db.scalar(
            select(func.count(Ticket.Ticket_ID)).filter(
                Ticket.Created_Date.between(start, end)
            )
        ) or 0

        active = await self.db.scalar(
            select(func.count(Ticket.Ticket_ID)).filter(
                Ticket.Ticket_Status_ID.notin_([3, 4])
            )
        ) or 0

        resolved = await self.db.scalar(
            select(func.count(Ticket.Ticket_ID)).filter(
                Ticket.Created_Date.between(start, end),
                Ticket.Ticket_Status_ID.in_([3, 4])
            )
        ) or 0

        return {
            "total_tickets": total,
            "active_tickets": active,
            "resolution_rate": resolved / max(total, 1),
        }

    async def _analyze_trends(
        self, metrics: Dict[str, Any], days: int
    ) -> Dict[str, TrendAnalysis]:
        prev_end = datetime.now(timezone.utc) - timedelta(days=days)
        prev_start = prev_end - timedelta(days=days)
        prev_metrics = await self._gather_all_metrics(prev_start, prev_end)

        change = (
            (metrics["total_tickets"] - prev_metrics["total_tickets"])
            / max(prev_metrics["total_tickets"], 1)
        ) * 100

        analysis = TrendAnalysis(
            direction=self._determine_trend_direction(change),
            change_percentage=change,
            velocity=change / days,
            prediction_next_period=metrics["total_tickets"] * (1 + change / 100),
            confidence=0.7,
        )
        return {"volume_trend": analysis}

    def _determine_trend_direction(self, change: float) -> TrendDirection:
        if abs(change) < 5:
            return TrendDirection.STABLE
        return TrendDirection.INCREASING if change > 0 else TrendDirection.DECREASING

    def _generate_insights(
        self, metrics: Dict[str, Any], trends: Dict[str, TrendAnalysis]
    ) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        trend = trends["volume_trend"]
        if trend.direction == TrendDirection.INCREASING and trend.change_percentage > 30:
            insights.append(
                {
                    "type": "warning",
                    "message": (
                        "Ticket volume is increasing rapidly; "
                        "consider scaling support resources."
                    ),
                }
            )
        return insights

    async def _generate_predictions(
        self, metrics: Dict[str, Any], trends: Dict[str, TrendAnalysis]
    ) -> Dict[str, Any]:
        trend = trends["volume_trend"]
        return {
            "expected_ticket_volume": int(trend.prediction_next_period),
            "confidence": f"{trend.confidence:.0%}",
        }
