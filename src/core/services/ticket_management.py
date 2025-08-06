"""Complete ticket lifecycle management."""

from __future__ import annotations

import logging
import html
from typing import Any, Sequence, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone, timedelta

from src.shared.schemas.search_params import TicketSearchParams
from src.shared.schemas.filters import AdvancedFilters, apply_advanced_filters
from pydantic import BaseModel
from sqlalchemy import select, or_, and_, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.exceptions import DatabaseError

from src.core.repositories.models import (
    Ticket,
    TicketMessage,
    TicketAttachment,
    TicketStatus as TicketStatusModel,
    VTicketMasterExpanded,
)

from .system_utilities import OperationResult, parse_search_datetime
from src.shared.utils.date_format import format_db_datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Semantic Filtering helpers
# ---------------------------------------------------------------------------
# Mapping of friendly status terms to their corresponding Ticket_Status_ID values
# These mappings allow semantic filtering when searching or updating tickets.

# State ID definitions
_OPEN_STATE_IDS = [1, 2, 4, 5, 6, 8]
_CLOSED_STATE_IDS = [3]

_STATUS_MAP = {
    # Closed and resolved tickets share the same state identifiers
    "closed": _CLOSED_STATE_IDS,
    "resolved": _CLOSED_STATE_IDS,
    # Tickets actively being worked may fall under multiple progress states
    "in_progress": [2, 5],
    "progress": [2, 5],
    # Waiting on user response
    "waiting": 4,
    # Pending/queued tickets
    "pending": 6,
}

_PRIORITY_MAP = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

_PRIORITY_LEVEL_TO_ID = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}


def apply_semantic_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Translate friendly filters into DB column filters."""
    if not filters:
        return {}

    translated: Dict[str, Any] = {}

    for key, value in filters.items():
        k = key.lower()

        if k in {"status", "ticket_status"}:
            if isinstance(value, str):
                v = value.lower()
                if v == "open":
                    translated["Ticket_Status_ID"] = _OPEN_STATE_IDS
                elif v == "closed":
                    translated["Ticket_Status_ID"] = _CLOSED_STATE_IDS
                else:
                    mapped = _STATUS_MAP.get(v, value)
                    translated["Ticket_Status_ID"] = mapped
            elif isinstance(value, list):
                ids: list[Any] = []
                for item in value:
                    if isinstance(item, str) and item.lower() == "open":
                        ids.extend(_OPEN_STATE_IDS)
                    elif isinstance(item, str) and item.lower() == "closed":
                        ids.extend(_CLOSED_STATE_IDS)
                    elif isinstance(item, str):
                        mapped = _STATUS_MAP.get(item.lower(), item)
                        if isinstance(mapped, list):
                            ids.extend(mapped)
                        else:
                            ids.append(mapped)
                    else:
                        ids.append(item)
                translated["Ticket_Status_ID"] = ids
            else:
                translated["Ticket_Status_ID"] = value

        elif k in {"priority", "priority_level"}:
            if isinstance(value, list):
                ids: list[Any] = []
                for item in value:
                    if isinstance(item, str):
                        canonical = _PRIORITY_MAP.get(item.lower(), item)
                        ids.append(_PRIORITY_LEVEL_TO_ID.get(canonical, item))
                    else:
                        ids.append(item)
                translated["Severity_ID"] = ids
            else:
                if isinstance(value, str):
                    canonical = _PRIORITY_MAP.get(value.lower(), value)
                    translated["Severity_ID"] = _PRIORITY_LEVEL_TO_ID.get(
                        canonical, value
                    )
                else:
                    translated["Severity_ID"] = value

        elif k == "assignee":
            translated["Assigned_Email"] = value

        elif k == "category":
            translated["Ticket_Category_ID"] = value

        else:
            translated[key] = value

    return translated


def _apply_semantic_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible wrapper for apply_semantic_filters."""
    return apply_semantic_filters(filters)


class TicketManager:
    """Handles all ticket CRUD and related operations."""

    # ------------------------------------------------------------------
    # Basic CRUD
    # ------------------------------------------------------------------
    async def get_ticket(
        self, db: AsyncSession, ticket_id: int
    ) -> VTicketMasterExpanded | None:
        """Get a single ticket by ID."""
        return await db.get(VTicketMasterExpanded, ticket_id)

    async def create_ticket(
        self, db: AsyncSession, ticket_obj: Ticket | Dict[str, Any]
    ) -> OperationResult[Ticket]:
        """Create a new ticket."""
        if isinstance(ticket_obj, dict):
            ticket_obj = Ticket(**ticket_obj)
        db.add(ticket_obj)
        try:
            await db.flush()
            await db.refresh(ticket_obj)
            return OperationResult(success=True, data=ticket_obj)
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("Failed to create ticket")
            return OperationResult(success=False, error=f"Failed to create ticket: {e}")

    async def update_ticket(
        self, db: AsyncSession, ticket_id: int, updates: BaseModel | Dict[str, Any]
    ) -> Ticket | None:
        """Update an existing ticket."""
        if isinstance(updates, BaseModel):
            updates = updates.model_dump(exclude_unset=True)
        
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        
        for key, value in updates.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        
        # Record when the ticket was last modified
        ticket.LastModified = datetime.now(timezone.utc)
        ticket.LastModfiedBy = "Gil AI"
        
        try:
            await db.flush()
            await db.refresh(ticket)
            logger.info("Updated ticket %s", ticket_id)
            return ticket
        except Exception:
            await db.rollback()
            logger.exception("Failed to update ticket %s", ticket_id)
            raise

    async def delete_ticket(self, db: AsyncSession, ticket_id: int) -> bool:
        """Delete a ticket."""
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

    # ------------------------------------------------------------------
    # Advanced querying
    # ------------------------------------------------------------------
    async def list_tickets(
        self,
        db: AsyncSession,
        filters: AdvancedFilters | Dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 10,
        sort: str | List[str] | None = None,
    ) -> Sequence[VTicketMasterExpanded]:
        """List tickets with advanced filtering and sorting."""
        query = select(VTicketMasterExpanded)
        sorted_applied = False
        
        if isinstance(filters, AdvancedFilters):
            query = apply_advanced_filters(query, filters, VTicketMasterExpanded)
            sorted_applied = bool(filters.sort)
        elif filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(VTicketMasterExpanded, key):
                    attr = getattr(VTicketMasterExpanded, key)
                    conditions.append(
                        attr.in_(value) if isinstance(value, list) else attr == value
                    )
            if conditions:
                query = query.filter(and_(*conditions))
        
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
                    order_columns.append(
                        attr.desc() if direction == "desc" else attr.asc()
                    )
            if order_columns:
                query = query.order_by(*order_columns)
            sorted_applied = True
        
        if not sorted_applied:
            query = query.order_by(VTicketMasterExpanded.Ticket_ID.desc())
        
        if skip:
            query = query.offset(skip)
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    def _escape_like_pattern(self, value: str) -> str:
        """Escape LIKE wildcard characters in a filter value."""
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _sanitize_search_input(self, query: str) -> str:
        """Basic sanitization of search input."""
        return html.escape(query).strip()

    async def search_tickets(
        self,
        db: AsyncSession,
        query: str | None,
        limit: int = 10,
        params: TicketSearchParams | None = None,
        *,
        user: str | None = None,
        days: int | None = None,
        created_after: datetime | str | None = None,
        created_before: datetime | str | None = None,
        status: str | int | None = None,
        priority: str | int | None = None,
        site_id: int | None = None,
        assigned_to: str | None = None,
        unassigned_only: bool = False,
        filters: Dict[str, Any] | None = None,
        skip: int = 0,
        sort: list[str] | None = None,
    ) -> tuple[List[VTicketMasterExpanded], int]:
        """Unified ticket search supporting advanced parameters."""
        
        sanitized = self._sanitize_search_input(query) if query else ""
        
        stmt = select(VTicketMasterExpanded)
        
        # Text search
        if sanitized:
            escaped = self._escape_like_pattern(sanitized)
            like = f"%{escaped}%"
            stmt = stmt.filter(
                or_(
                    VTicketMasterExpanded.Subject.ilike(like, escape="\\"),
                    VTicketMasterExpanded.Ticket_Body.ilike(like, escape="\\"),
                )
            )
        
        # User search
        if user:
            ident = user.lower().strip()
            stmt = stmt.filter(
                or_(
                    func.lower(VTicketMasterExpanded.Ticket_Contact_Name) == ident,
                    func.lower(VTicketMasterExpanded.Ticket_Contact_Email) == ident,
                    func.lower(VTicketMasterExpanded.Assigned_Name) == ident,
                    func.lower(VTicketMasterExpanded.Assigned_Email) == ident,
                )
            )
        
        # Process params
        filters_dict = params.model_dump(exclude_none=True) if params else {}
        sort_value = filters_dict.pop("sort", None)
        param_after = filters_dict.pop("created_after", None)
        param_before = filters_dict.pop("created_before", None)
        
        if created_after is None:
            created_after = param_after
        if created_before is None:
            created_before = param_before
        
        # Apply semantic filters
        if status is not None:
            filters_dict.update(apply_semantic_filters({"status": status}))
        if priority is not None:
            filters_dict.update(apply_semantic_filters({"priority": priority}))
        if site_id is not None:
            filters_dict["Site_ID"] = site_id
        if assigned_to:
            filters_dict["Assigned_Email"] = assigned_to
        if filters:
            filters_dict.update(apply_semantic_filters(filters))
        
        if unassigned_only:
            stmt = stmt.filter(VTicketMasterExpanded.Assigned_Email.is_(None))
        
        # Apply filters
        for key, value in filters_dict.items():
            if hasattr(VTicketMasterExpanded, key):
                col = getattr(VTicketMasterExpanded, key)
                if isinstance(value, list):
                    stmt = stmt.filter(col.in_(value))
                else:
                    stmt = stmt.filter(col == value)
        
        # Date filtering
        if created_after:
            if isinstance(created_after, str):
                created_after = parse_search_datetime(created_after)
            stmt = stmt.filter(VTicketMasterExpanded.Created_Date >= created_after)
        elif days is not None and days >= 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            # Normalize to millisecond precision for SQL Server
            if cutoff.microsecond % 1000:
                cutoff = cutoff.replace(microsecond=(cutoff.microsecond // 1000) * 1000)
            stmt = stmt.filter(VTicketMasterExpanded.Created_Date >= cutoff)
        
        if created_before:
            if isinstance(created_before, str):
                created_before = parse_search_datetime(created_before)
            stmt = stmt.filter(VTicketMasterExpanded.Created_Date <= created_before)
        
        # Sorting
        order_list: list[Any] = []
        if sort:
            for key in sort:
                direction = "asc"
                column = key
                if key.startswith("-"):
                    column = key[1:]
                    direction = "desc"
                elif " " in key:
                    column, dir_part = key.rsplit(" ", 1)
                    if dir_part.lower() in {"asc", "desc"}:
                        direction = dir_part.lower()
                if hasattr(VTicketMasterExpanded, column):
                    attr = getattr(VTicketMasterExpanded, column)
                    order_list.append(
                        attr.desc() if direction == "desc" else attr.asc()
                    )
        elif sort_value:
            if sort_value == "oldest":
                order_list.append(VTicketMasterExpanded.Created_Date.asc())
            else:
                order_list.append(VTicketMasterExpanded.Created_Date.desc())
        else:
            order_list.append(VTicketMasterExpanded.Created_Date.desc())
        
        if order_list:
            stmt = stmt.order_by(*order_list)
        
        # Count total before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = await db.scalar(count_stmt) or 0
        
        # Apply pagination
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        
        # Execute query
        result = await db.execute(stmt)
        records = list(result.scalars().all())
        
        return records, total_count

    async def get_tickets_by_user(
        self,
        db: AsyncSession,
        identifier: str,
        *,
        skip: int = 0,
        limit: int | None = 100,
        status: str | None = None,
        filters: Dict[str, Any] | None = None,
    ) -> List[VTicketMasterExpanded]:
        """Get all tickets associated with a user."""
        ident = identifier.lower()
        
        # Find tickets where user is contact or assignee
        contact_stmt = select(VTicketMasterExpanded.Ticket_ID).filter(
            or_(
                func.lower(VTicketMasterExpanded.Ticket_Contact_Name) == ident,
                func.lower(VTicketMasterExpanded.Ticket_Contact_Email) == ident,
                func.lower(VTicketMasterExpanded.Assigned_Name) == ident,
                func.lower(VTicketMasterExpanded.Assigned_Email) == ident,
            )
        )
        result = await db.execute(contact_stmt)
        ticket_ids = {row[0] for row in result.all()}
        
        # Find tickets where user sent messages
        msg_stmt = select(TicketMessage.Ticket_ID).filter(
            or_(
                func.lower(TicketMessage.SenderUserName) == ident,
                func.lower(TicketMessage.SenderUserCode) == ident,
            )
        )
        result = await db.execute(msg_stmt)
        ticket_ids.update(row[0] for row in result.all())
        
        if not ticket_ids:
            return []
        
        # Build query for tickets
        query = select(VTicketMasterExpanded).filter(
            VTicketMasterExpanded.Ticket_ID.in_(ticket_ids)
        )
        query = query.order_by(VTicketMasterExpanded.Ticket_ID)
        
        # Apply status filter
        if status:
            s = status.lower()
            if s == "open":
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(_OPEN_STATE_IDS)
                )
            elif s == "closed":
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(_CLOSED_STATE_IDS)
                )
            elif s in {"in_progress", "progress"}:
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(
                        _STATUS_MAP["in_progress"]
                    )
                )
        
        # Apply additional filters
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(VTicketMasterExpanded, key):
                    attr = getattr(VTicketMasterExpanded, key)
                    conditions.append(
                        attr.in_(value) if isinstance(value, list) else attr == value
                    )
            if conditions:
                query = query.filter(and_(*conditions))
        
        # Apply pagination
        if skip:
            query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_tickets_by_timeframe(
        self,
        db: AsyncSession,
        *,
        status: str | None = None,
        days: int = 7,
        limit: int = 10,
    ) -> List[VTicketMasterExpanded]:
        """Get tickets within a specific timeframe."""
        query = select(VTicketMasterExpanded)
        
        # Apply status filter
        if status:
            s = status.lower()
            if s == "open":
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(_OPEN_STATE_IDS)
                )
            elif s == "closed":
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(_CLOSED_STATE_IDS)
                )
            elif s in {"in_progress", "progress"}:
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(
                        _STATUS_MAP["in_progress"]
                    )
                )
        
        # Apply time filter
        if days is not None and days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            # Normalize to millisecond precision for SQL Server
            if cutoff.microsecond % 1000:
                cutoff = cutoff.replace(microsecond=(cutoff.microsecond // 1000) * 1000)
            query = query.filter(VTicketMasterExpanded.Created_Date >= cutoff)
        
        query = query.order_by(VTicketMasterExpanded.Created_Date.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Messages & Attachments
    # ------------------------------------------------------------------
    async def get_messages(
        self, db: AsyncSession, ticket_id: int
    ) -> List[TicketMessage]:
        """Get all messages for a ticket."""
        result = await db.execute(
            select(TicketMessage)
            .filter(TicketMessage.Ticket_ID == ticket_id)
            .order_by(TicketMessage.DateTimeStamp)
        )
        return list(result.scalars().all())

    async def post_message(
        self,
        db: AsyncSession,
        ticket_id: int,
        message: str,
        sender_code: str | None = None,
        sender_name: str | None = None,
    ) -> TicketMessage:
        """Post a new message to a ticket."""
        msg = TicketMessage(
            Ticket_ID=ticket_id,
            Message=message,
            SenderUserCode=sender_code or "GilAI@heinzcorps.com",
            SenderUserName=sender_name or "Gil AI",
            DateTimeStamp=datetime.now(timezone.utc),
        )
        db.add(msg)
        try:
            await db.commit()
            await db.refresh(msg)
            logger.info("Posted message to ticket %s", ticket_id)
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("Failed to save ticket message for %s", ticket_id)
            raise DatabaseError("Failed to save message", details=str(e))
        return msg

    async def get_attachments(
        self, db: AsyncSession, ticket_id: int
    ) -> List[TicketAttachment]:
        """Get all attachments for a ticket."""
        result = await db.execute(
            select(TicketAttachment).filter(TicketAttachment.Ticket_ID == ticket_id)
        )
        return list(result.scalars().all())


# ----------------------------------------------------------------------
# Simplified smart search and creation helpers from TicketTools
# ----------------------------------------------------------------------
class TicketPriority(str, Enum):
    """Ticket priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketStatus(str, Enum):
    """Ticket status values."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_ON_USER = "waiting_on_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class TicketSearchResult:
    """Structured ticket search result."""
    ticket_id: int
    subject: str
    summary: str
    status: str
    priority: str
    assigned_to: Optional[str]
    created_date: str
    relevance_score: float

    def to_llm_format(self) -> Dict[str, Any]:
        """Convert to LLM-friendly format."""
        return {
            "id": self.ticket_id,
            "title": self.subject,
            "preview": self.summary,
            "status": self.status,
            "priority": self.priority,
            "assigned_to": self.assigned_to,
            "created": self.created_date,
            "relevance": self.relevance_score,
        }


class TicketTools:
    """Enhanced ticket operations with smart search features."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.manager = TicketManager()

    async def search_tickets_smart(
        self,
        query: str,
        include_closed: bool = False,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Smart ticket search with relevance scoring."""
        like = f"%{query}%"
        stmt = select(VTicketMasterExpanded).filter(
            or_(
                VTicketMasterExpanded.Subject.ilike(like),
                VTicketMasterExpanded.Ticket_Body.ilike(like),
            )
        )
        
        if not include_closed:
            stmt = stmt.filter(
                ~VTicketMasterExpanded.Ticket_Status_ID.in_(_CLOSED_STATE_IDS)
            )
        
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        tickets = result.scalars().all()
        
        search_results: List[TicketSearchResult] = []
        for ticket in tickets:
            search_results.append(
                TicketSearchResult(
                    ticket_id=ticket.Ticket_ID,
                    subject=ticket.Subject or "",
                    summary=(
                        (ticket.Ticket_Body[:200] + "...")
                        if ticket.Ticket_Body and len(ticket.Ticket_Body) > 200
                        else (ticket.Ticket_Body or "")
                    ),
                    status=ticket.Ticket_Status_Label or "Unknown",
                    priority=ticket.Priority_Level or "Medium",
                    assigned_to=ticket.Assigned_Name,
                    created_date=(
                        format_db_datetime(ticket.Created_Date)
                        if ticket.Created_Date
                        else ""
                    ),
                    relevance_score=1.0,
                )
            )
        
        return {
            "query": query,
            "results_count": len(search_results),
            "results": [r.to_llm_format() for r in search_results],
        }

    async def create_ticket_with_intelligence(
        self,
        title: str,
        description: str,
        contact: Dict[str, str],
    ) -> OperationResult[Ticket]:
        """Create a ticket with intelligent defaults."""
        ticket = Ticket(
            Subject=title,
            Ticket_Body=description,
            Ticket_Contact_Name=contact.get("name"),
            Ticket_Contact_Email=contact.get("email"),
            Created_Date=datetime.now(timezone.utc),
            Ticket_Status_ID=1,  # Default to "Open"
        )
        return await self.manager.create_ticket(self.db, ticket)


__all__ = [
    "TicketManager",
    "TicketTools",
    "TicketPriority",
    "TicketStatus",
    "TicketSearchResult",
    "_OPEN_STATE_IDS",
    "_CLOSED_STATE_IDS",
    "apply_semantic_filters",
    "_apply_semantic_filters",
]