"""Analytics helpers for summarizing ticket data."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, text, and_, or_, case
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta, timezone
import statistics

import logging

from db.models import Ticket, TicketStatus, Site, TicketMessage
from schemas.analytics import (
    StatusCount,
    SiteOpenCount,
    UserOpenCount,
    WaitingOnUserCount,
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


async def tickets_by_status(
    db: AsyncSession,
) -> List[tuple[int | None, str | None, int]]:
    """Return counts of tickets grouped by status.

    Each :class:`StatusCount` contains ``status_id``, ``status_label`` and
    ``count`` fields.
    """

    logger.info("Calculating tickets by status")
    result = await db.execute(
        select(
            Ticket.Ticket_Status_ID,
            TicketStatus.Label,
            func.count(Ticket.Ticket_ID),
        )
        .join(TicketStatus, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
        .group_by(Ticket.Ticket_Status_ID, TicketStatus.Label)
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


async def open_tickets_by_site(
    db: AsyncSession,
) -> List[tuple[int | None, str | None, int]]:
    """Return open ticket counts grouped by site.

    Each :class:`SiteOpenCount` contains ``site_id``, ``site_label`` and
    ``count`` fields for tickets not closed (status != 3).
    """

    logger.info("Calculating open tickets by site")
    result = await db.execute(
        select(
            Ticket.Site_ID,
            Site.Label,
            func.count(Ticket.Ticket_ID),
        )
        .join(Site, Ticket.Site_ID == Site.ID, isouter=True)
        .filter(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Site_ID, Site.Label)
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


async def sla_breaches(
    db: AsyncSession,
    sla_days: int = 2,
    filters: dict[str, Any] | None = None,
    status_ids: list[int] | None = None,
) -> int:
    """Count tickets older than ``sla_days`` with optional filtering."""
    from datetime import datetime, timedelta, UTC

    logger.info(
        "Counting SLA breaches older than %s days with filters=%s statuses=%s",
        sla_days,
        filters,
        status_ids,
    )
    cutoff = datetime.now(UTC) - timedelta(days=sla_days)

    query = select(func.count(Ticket.Ticket_ID)).filter(Ticket.Created_Date < cutoff)

    if status_ids is not None:
        query = query.filter(Ticket.Ticket_Status_ID.in_(status_ids))
    else:
        query = query.filter(Ticket.Ticket_Status_ID != 3)

    if filters:
        for key, value in filters.items():
            if hasattr(Ticket, key):
                query = query.filter(getattr(Ticket, key) == value)

    result = await db.execute(query)
    return result.scalar_one()


async def open_tickets_by_user(db: AsyncSession) -> List[tuple[str | None, int]]:
    """Return open ticket counts grouped by assigned technician.

    Each :class:`UserOpenCount` contains ``assigned_email`` and ``count``
    fields for tickets not closed.
    """

    logger.info("Calculating open tickets by user")
    result = await db.execute(
        select(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Assigned_Email)
    )
    return [(row[0], row[1]) for row in result.all()]


async def tickets_waiting_on_user(db: AsyncSession) -> List[tuple[str | None, int]]:
    """Return counts of tickets awaiting a user response.

    Each :class:`WaitingOnUserCount` contains ``contact_email`` and ``count``
    fields for tickets where status is ``4``.
    """

    logger.info("Calculating tickets waiting on user")
    result = await db.execute(
        select(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID == 4)
        .group_by(Ticket.Ticket_Contact_Email)
    )
    return [(row[0], row[1]) for row in result.all()]


class AnalyticsTools:
    """Enhanced analytics helper with trends and predictions."""

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

        dashboard = {
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
        metrics: Dict[str, Any] = {}
        total_stmt = select(func.count(Ticket.Ticket_ID)).filter(
            Ticket.Created_Date.between(start, end)
        )
        metrics["total_tickets"] = await self.db.scalar(total_stmt) or 0
        active_stmt = select(func.count(Ticket.Ticket_ID)).filter(
            Ticket.Ticket_Status_ID.notin_([3, 4])
        )
        metrics["active_tickets"] = await self.db.scalar(active_stmt) or 0
        resolved_stmt = select(func.count(Ticket.Ticket_ID)).filter(
            Ticket.Created_Date.between(start, end), Ticket.Ticket_Status_ID.in_([3, 4])
        )
        resolved = await self.db.scalar(resolved_stmt) or 0
        metrics["resolution_rate"] = resolved / max(metrics["total_tickets"], 1)
        return metrics

    async def _analyze_trends(
        self, metrics: Dict[str, Any], days: int
    ) -> Dict[str, TrendAnalysis]:
        end_prev = datetime.now(timezone.utc) - timedelta(days=days)
        start_prev = end_prev - timedelta(days=days)
        prev_metrics = await self._gather_all_metrics(start_prev, end_prev)

        change = (
            (metrics["total_tickets"] - prev_metrics["total_tickets"])
            / max(prev_metrics["total_tickets"], 1)
        ) * 100
        trend = TrendAnalysis(
            direction=self._determine_trend_direction(change),
            change_percentage=change,
            velocity=change / days,
            prediction_next_period=metrics["total_tickets"] * (1 + change / 100),
            confidence=0.7,
        )
        return {"volume_trend": trend}

    def _determine_trend_direction(self, change: float) -> TrendDirection:
        if abs(change) < 5:
            return TrendDirection.STABLE
        return TrendDirection.INCREASING if change > 0 else TrendDirection.DECREASING

    def _generate_insights(
        self, metrics: Dict[str, Any], trends: Dict[str, TrendAnalysis]
    ) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        if (
            trends["volume_trend"].direction == TrendDirection.INCREASING
            and trends["volume_trend"].change_percentage > 30
        ):
            insights.append(
                {
                    "type": "warning",
                    "message": "Ticket volume increasing rapidly",
                }
            )
        return insights

    async def _generate_predictions(
        self, metrics: Dict[str, Any], trends: Dict[str, TrendAnalysis]
    ) -> Dict[str, Any]:
        return {
            "expected_ticket_volume": int(
                trends["volume_trend"].prediction_next_period
            ),
            "confidence": f"{trends['volume_trend'].confidence:.0%}",
        }
