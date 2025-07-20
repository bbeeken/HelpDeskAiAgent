"""Database helpers for manipulating tickets."""

from __future__ import annotations

import logging
from typing import Any, Sequence, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel

from sqlalchemy import select
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Ticket, VTicketMasterExpanded

logger = logging.getLogger(__name__)


async def get_ticket_expanded(
    db: AsyncSession, ticket_id: int
) -> VTicketMasterExpanded | None:
    """Return a ticket from the expanded view."""
    return await db.get(VTicketMasterExpanded, ticket_id)


async def list_tickets_expanded(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    filters: dict[str, Any] | None = None,
    sort: str | list[str] | None = None,
) -> Sequence[VTicketMasterExpanded]:
    """Return tickets with related labels from the expanded view."""

    query = select(VTicketMasterExpanded)

    if filters:
        for key, value in filters.items():
            if hasattr(VTicketMasterExpanded, key):
                query = query.filter(getattr(VTicketMasterExpanded, key) == value)

    if sort:
        if isinstance(sort, str):
            sort = [sort]

        order_columns = []
        for s in sort:
            direction = "asc"
            column = s
            if s.startswith("-"):
                column = s[1:]
                direction = "desc"
            elif " " in s:
                column, dir_part = s.rsplit(" ", 1)
                if dir_part.lower() in {"asc", "desc"}:
                    direction = dir_part.lower()
            if hasattr(VTicketMasterExpanded, column):
                attr = getattr(VTicketMasterExpanded, column)
                order_columns.append(attr.desc() if direction == "desc" else attr.asc())
        if order_columns:
            query = query.order_by(*order_columns)
    else:
        query = query.order_by(VTicketMasterExpanded.Ticket_ID)

    if skip:
        query = query.offset(skip)
    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def search_tickets_expanded(
    db: AsyncSession, query: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Search tickets in the expanded view by subject or body.

    Results include only a subset of fields and skip tickets with very large
    bodies. Each dictionary contains ``Ticket_ID``, ``Subject``, a ``body_preview``
    truncated to 200 characters, ``status_label`` and ``priority_level``.
    """

    like = f"%{query}%"

    result = await db.execute(
        select(VTicketMasterExpanded)
        .filter(
            (VTicketMasterExpanded.Subject.ilike(like))
            | (VTicketMasterExpanded.Ticket_Body.ilike(like))
        )
        .limit(limit)
    )

    summaries: list[dict[str, Any]] = []
    for row in result.scalars().all():
        body = row.Ticket_Body or ""
        if len(body) > 2000:
            continue
        summaries.append(
            {
                "Ticket_ID": row.Ticket_ID,
                "Subject": row.Subject,
                "body_preview": body[:200],
                "status_label": row.Ticket_Status_Label,
                "priority_level": row.Priority_Level,
            }
        )

    return summaries


async def create_ticket(db: AsyncSession, ticket_obj: Ticket) -> Ticket:
    db.add(ticket_obj)
    try:
        await db.commit()
        await db.refresh(ticket_obj)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception("Failed to create ticket")
        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {e}")
    return ticket_obj


async def update_ticket(db: AsyncSession, ticket_id: int, updates) -> Ticket | None:
    """Update a ticket with a mapping or Pydantic model."""
    if isinstance(updates, BaseModel):
        updates = updates.model_dump(exclude_unset=True)

    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        return None

    for key, value in updates.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)

    try:
        await db.commit()
        await db.refresh(ticket)
        logger.info("Updated ticket %s", ticket_id)
        return ticket
    except Exception:
        await db.rollback()
        logger.exception("Failed to update ticket %s", ticket_id)
        raise


async def delete_ticket(db: AsyncSession, ticket_id: int) -> bool:
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        return False
    try:
        await db.delete(ticket)
        await db.commit()
        logger.info("Deleted ticket %s", ticket_id)
        return True
    except Exception:
        await db.rollback()
        logger.exception("Failed to delete ticket %s", ticket_id)
        raise


# ---------------------------------------------------------------------------
# Enhanced ticket tools
# ---------------------------------------------------------------------------


class TicketPriority(str, Enum):
    """Enumerated priority levels for tickets."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketStatus(str, Enum):
    """Enumerated ticket workflow statuses."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_ON_USER = "waiting_on_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class TicketSearchResult:
    """Structured search result data for LLM use."""

    ticket_id: int
    subject: str
    summary: str
    status: str
    priority: str
    assigned_to: Optional[str]
    created_date: str
    relevance_score: float

    def to_llm_format(self) -> Dict[str, Any]:
        return {
            "id": self.ticket_id,
            "title": self.subject,
            "preview": self.summary,
            "status": {
                "value": self.status,
                "is_open": self.status not in ["resolved", "closed"],
            },
            "priority": {
                "value": self.priority,
                "is_urgent": self.priority in ["critical", "high"],
            },
            "assignment": {
                "assigned_to": self.assigned_to,
                "is_assigned": bool(self.assigned_to),
            },
            "timing": {
                "created": self.created_date,
                "age_hours": self._calculate_age_hours(),
            },
            "search_relevance": self.relevance_score,
        }

    def _calculate_age_hours(self) -> float:
        created = datetime.fromisoformat(self.created_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - created).total_seconds() / 3600


class TicketTools:
    """Enhanced ticket operations with LLM friendly helpers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_tickets_smart(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        include_closed: bool = False,
    ) -> Dict[str, Any]:
        """Perform a smart natural language ticket search."""
        try:
            search_context = self._parse_search_query(query)

            stmt = select(VTicketMasterExpanded)
            conditions = []

            if search_context.get("keywords"):
                keywords = search_context["keywords"]
                text_conditions = []
                for kw in keywords:
                    pattern = f"%{kw}%"
                    text_conditions.extend(
                        [
                            VTicketMasterExpanded.Subject.ilike(pattern),
                            VTicketMasterExpanded.Ticket_Body.ilike(pattern),
                        ]
                    )
                conditions.append(or_(*text_conditions))

            if search_context.get("priority"):
                priority_map = {
                    "critical": 1,
                    "urgent": 1,
                    "high": 2,
                    "medium": 3,
                    "normal": 3,
                    "low": 4,
                }
                priority_id = priority_map.get(search_context["priority"].lower())
                if priority_id:
                    conditions.append(VTicketMasterExpanded.Priority_ID == priority_id)

            if not include_closed:
                conditions.append(VTicketMasterExpanded.Ticket_Status_ID != 3)

            if search_context.get("assigned_to"):
                conditions.append(
                    VTicketMasterExpanded.Assigned_Name.ilike(
                        f"%{search_context['assigned_to']}%"
                    )
                )
            elif search_context.get("unassigned"):
                conditions.append(VTicketMasterExpanded.Assigned_Email.is_(None))

            if conditions:
                stmt = stmt.filter(and_(*conditions))

            stmt = stmt.order_by(VTicketMasterExpanded.Created_Date.desc()).limit(limit)

            result = await self.db.execute(stmt)
            tickets = result.scalars().all()

            search_results: List[TicketSearchResult] = []
            for ticket in tickets:
                relevance = self._calculate_relevance(ticket, search_context)
                search_results.append(
                    TicketSearchResult(
                        ticket_id=ticket.Ticket_ID,
                        subject=ticket.Subject,
                        summary=(
                            ticket.Ticket_Body[:200] + "..."
                            if ticket.Ticket_Body and len(ticket.Ticket_Body) > 200
                            else ticket.Ticket_Body
                        ),
                        status=ticket.Ticket_Status_Label or "Unknown",
                        priority=self._map_priority_label(ticket.Priority_Level),
                        assigned_to=ticket.Assigned_Name,
                        created_date=(
                            ticket.Created_Date.isoformat()
                            if ticket.Created_Date
                            else ""
                        ),
                        relevance_score=relevance,
                    )
                )

            search_results.sort(key=lambda x: x.relevance_score, reverse=True)

            response = {
                "query": query,
                "interpretation": search_context,
                "results_count": len(search_results),
                "results": [r.to_llm_format() for r in search_results],
                "search_metadata": {
                    "included_closed": include_closed,
                    "limit_applied": limit,
                    "filters_applied": bool(conditions),
                },
            }

            return response
        except Exception as e:
            logger.exception("Smart search failed for query: %s", query)
            return {
                "error": True,
                "error_type": "search_failed",
                "error_message": str(e),
            }

    def _parse_search_query(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        context: Dict[str, Any] = {"original_query": query}

        priority_keywords = {
            "critical": ["critical", "emergency", "down", "outage"],
            "high": ["urgent", "high priority", "asap", "important"],
            "medium": ["medium", "normal"],
            "low": ["low priority", "minor"],
        }

        for p, keywords in priority_keywords.items():
            if any(kw in query_lower for kw in keywords):
                context["priority"] = p
                break

        if "unassigned" in query_lower or "not assigned" in query_lower:
            context["unassigned"] = True
        elif "assigned to" in query_lower:
            parts = query_lower.split("assigned to")
            if len(parts) > 1:
                name = parts[1].strip().split()[0]
                context["assigned_to"] = name

        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "ticket",
            "tickets",
            "issue",
            "issues",
            "problem",
            "problems",
        }

        words = query_lower.split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        if keywords:
            context["keywords"] = keywords

        return context

    def _map_priority_label(self, priority_level: Optional[str]) -> str:
        mapping = {
            "Critical": "critical",
            "High": "high",
            "Medium": "medium",
            "Normal": "medium",
            "Low": "low",
        }
        if not priority_level:
            return "medium"
        return mapping.get(priority_level, "medium")

    def _calculate_relevance(
        self, ticket: VTicketMasterExpanded, context: Dict[str, Any]
    ) -> float:
        score = 0.5
        if context.get("keywords"):
            subject = ticket.Subject.lower() if ticket.Subject else ""
            body = ticket.Ticket_Body.lower() if ticket.Ticket_Body else ""
            for kw in context["keywords"]:
                if kw in subject:
                    score += 0.3
                elif kw in body:
                    score += 0.1
        if context.get("priority"):
            if (
                self._map_priority_label(ticket.Priority_Level).lower()
                == context["priority"]
            ):
                score += 0.2
        if ticket.Created_Date:
            age_days = (datetime.now(timezone.utc) - ticket.Created_Date).days
            if age_days < 1:
                score += 0.2
            elif age_days < 7:
                score += 0.1
        return min(score, 1.0)

    def _get_search_suggestions(
        self, results: List[TicketSearchResult], query: str
    ) -> List[str]:
        suggestions: List[str] = []
        if not results:
            suggestions.append("Try broadening your search terms")
            suggestions.append("Check if tickets might be closed")
            suggestions.append("Search by ticket ID for specific tickets")
        elif len(results) == 1:
            suggestions.append(
                f"Found exact match. Use ticket ID {results[0].ticket_id} for direct access"
            )
        elif len(results) > 5:
            suggestions.append(
                "Many results found. Try adding filters like priority or status"
            )
        return suggestions

    async def create_ticket_with_intelligence(
        self,
        title: str,
        description: str,
        contact_name: str,
        contact_email: str,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            analysis = await self._analyze_ticket_content(title, description)
            ticket = Ticket(
                Subject=title,
                Ticket_Body=description,
                Ticket_Contact_Name=contact_name,
                Ticket_Contact_Email=contact_email,
                Ticket_Status_ID=1,
                Priority_ID=analysis.get("suggested_priority_id", 3),
                Ticket_Category_ID=analysis.get("suggested_category_id"),
                Created_Date=datetime.now(timezone.utc),
                **kwargs,
            )

            self.db.add(ticket)
            await self.db.commit()
            await self.db.refresh(ticket)

            response = {
                "success": True,
                "ticket": {
                    "id": ticket.Ticket_ID,
                    "subject": ticket.Subject,
                    "status": "Open",
                    "priority": analysis.get("suggested_priority", "medium"),
                },
                "ai_analysis": analysis,
            }
            return response
        except Exception as e:
            logger.exception("Failed to create ticket with intelligence")
            return {
                "success": False,
                "error": True,
                "error_message": str(e),
            }

    async def _analyze_ticket_content(
        self, title: str, description: str
    ) -> Dict[str, Any]:
        content = f"{title} {description}".lower()
        analysis: Dict[str, Any] = {}

        urgency_indicators: List[str] = []
        if any(word in content for word in ["down", "outage", "critical"]):
            analysis["suggested_priority_id"] = 1
            analysis["suggested_priority"] = "critical"
            urgency_indicators.append("System down")
        elif any(word in content for word in ["urgent", "asap"]):
            analysis["suggested_priority_id"] = 2
            analysis["suggested_priority"] = "high"
        else:
            analysis["suggested_priority_id"] = 3
            analysis["suggested_priority"] = "medium"

        analysis["urgency_indicators"] = urgency_indicators

        category_keywords = {
            "hardware": ["printer", "laptop", "screen"],
            "software": ["application", "install", "update"],
            "network": ["internet", "network", "wifi", "vpn"],
            "email": ["email", "outlook", "inbox"],
        }
        for category, kws in category_keywords.items():
            if any(kw in content for kw in kws):
                analysis["suggested_category"] = category.title()
                break

        return analysis
