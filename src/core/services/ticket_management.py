"""Complete ticket lifecycle management."""

from __future__ import annotations

import logging
import html
import re
from typing import Any, Sequence, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone, timedelta

from src.shared.schemas.search_params import TicketSearchParams
from src.shared.schemas.filters import AdvancedFilters, apply_advanced_filters
from pydantic import BaseModel
from sqlalchemy import select, or_, and_, func, text
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

from .system_utilities import OperationResult

logger = logging.getLogger(__name__)


class TicketManager:
    """Handles all ticket CRUD and related operations."""

    # ------------------------------------------------------------------
    # Basic CRUD
    # ------------------------------------------------------------------
    async def get_ticket(self, db: AsyncSession, ticket_id: int) -> VTicketMasterExpanded | None:
        return await db.get(VTicketMasterExpanded, ticket_id)

    async def create_ticket(
        self, db: AsyncSession, ticket_obj: Ticket | Dict[str, Any]
    ) -> OperationResult[Ticket]:
        if isinstance(ticket_obj, dict):
            ticket_obj = Ticket(**ticket_obj)
        db.add(ticket_obj)
        try:
            await db.commit()
            await db.refresh(ticket_obj)
            return OperationResult(success=True, data=ticket_obj)
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("Failed to create ticket")
            return OperationResult(success=False, error=f"Failed to create ticket: {e}")

    async def update_ticket(
        self, db: AsyncSession, ticket_id: int, updates: BaseModel | Dict[str, Any]
    ) -> Ticket | None:
        if isinstance(updates, BaseModel):
            updates = updates.model_dump(exclude_unset=True)
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        for key, value in updates.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        ticket.LastModified = datetime.now(timezone.utc)
        try:
            await db.commit()
            await db.refresh(ticket)
            logger.info("Updated ticket %s", ticket_id)
            return ticket
        except Exception:
            await db.rollback()
            logger.exception("Failed to update ticket %s", ticket_id)
            raise

    async def delete_ticket(self, db: AsyncSession, ticket_id: int) -> bool:
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
                    conditions.append(attr.in_(value) if isinstance(value, list) else attr == value)
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
                    order_columns.append(attr.desc() if direction == "desc" else attr.asc())
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
        return (
            value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )

    def _sanitize_search_input(self, query: str) -> str:


        """Basic sanitization of search input."""
        return html.escape(query).strip()





    async def search_tickets(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 10,
        params: TicketSearchParams | None = None,
    ) -> List[dict[str, Any]]:
        sanitized = self._sanitize_search_input(query)
        if not sanitized:
            return []
        like = f"%{sanitized}%"
        stmt = select(VTicketMasterExpanded).filter(
            and_(
                or_(
                    VTicketMasterExpanded.Subject.ilike(like),
                    VTicketMasterExpanded.Ticket_Body.ilike(like),
                ),
                func.length(VTicketMasterExpanded.Ticket_Body) <= 2000,
            )
        )
        filters = params.model_dump(exclude_none=True) if params else {}
        sort_value = filters.pop("sort", None)
        for key, value in filters.items():
            if hasattr(VTicketMasterExpanded, key):
                col = getattr(VTicketMasterExpanded, key)
                if isinstance(value, str):
                    escaped_value = self._escape_like_pattern(value)
                    stmt = stmt.filter(col.ilike(f"%{escaped_value}%"))
                else:
                    stmt = stmt.filter(col == value)
        if sort_value == "oldest":
            stmt = stmt.order_by(VTicketMasterExpanded.Created_Date.asc())
        else:
            stmt = stmt.order_by(VTicketMasterExpanded.Created_Date.desc())
        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        summaries: list[dict[str, Any]] = [
            {
                "Ticket_ID": row.Ticket_ID,
                "Subject": row.Subject,
                "body_preview": (row.Ticket_Body or "")[:200],
                "status_label": row.Ticket_Status_Label,
                "priority_level": row.Priority_Level,
            }
            for row in result.scalars().all()
        ]
        return summaries

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
        ident = identifier.lower()
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
        query = select(VTicketMasterExpanded).filter(
            VTicketMasterExpanded.Ticket_ID.in_(ticket_ids)
        )  # noqa: E501
        query = query.order_by(VTicketMasterExpanded.Ticket_ID)
        if status:
            query = query.join(
                TicketStatusModel,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatusModel.ID,
                isouter=True,
            )
            s = status.lower()
            if s == "open":
                query = query.filter(
                    or_(
                        TicketStatusModel.Label.ilike("%open%"),
                        TicketStatusModel.Label.ilike("%progress%"),
                    )
                )
            elif s == "closed":
                query = query.filter(
                    or_(
                        TicketStatusModel.Label.ilike("%closed%"),
                        TicketStatusModel.Label.ilike("%resolved%"),
                    )
                )
            elif s == "progress":
                query = query.filter(TicketStatusModel.Label.ilike("%progress%"))
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(VTicketMasterExpanded, key):
                    attr = getattr(VTicketMasterExpanded, key)
                    conditions.append(attr.in_(value) if isinstance(value, list) else attr == value)
            if conditions:
                query = query.filter(and_(*conditions))
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
        query = select(VTicketMasterExpanded).join(
            TicketStatusModel,
            VTicketMasterExpanded.Ticket_Status_ID == TicketStatusModel.ID,
            isouter=True,
        )
        if status:
            s = status.lower()
            if s == "open":
                query = query.filter(
                    or_(
                        TicketStatusModel.Label.ilike("%open%"),
                        TicketStatusModel.Label.ilike("%progress%"),
                    )
                )
            elif s == "closed":
                query = query.filter(
                    or_(
                        TicketStatusModel.Label.ilike("%closed%"),
                        TicketStatusModel.Label.ilike("%resolved%"),
                    )
                )
        if days is not None and days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(VTicketMasterExpanded.Created_Date >= cutoff)
        query = query.order_by(VTicketMasterExpanded.Created_Date.desc())
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Messages & Attachments
    # ------------------------------------------------------------------
    async def get_messages(self, db: AsyncSession, ticket_id: int) -> List[TicketMessage]:
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
        sender_code: str,
        sender_name: str,
    ) -> TicketMessage:
        msg = TicketMessage(
            Ticket_ID=ticket_id,
            Message=message,
            SenderUserCode='GilAI@heinzcorps.com',
            SenderUserName='Gil AI',
            DateTimeStamp=datetime.now(),
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

    async def get_attachments(self, db: AsyncSession, ticket_id: int) -> List[TicketAttachment]:
        result = await db.execute(
            select(TicketAttachment).filter(TicketAttachment.Ticket_ID == ticket_id)
        )
        return list(result.scalars().all())


# ----------------------------------------------------------------------
# Simplified smart search and creation helpers from TicketTools
# ----------------------------------------------------------------------
class TicketPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_ON_USER = "waiting_on_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class TicketSearchResult:
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

    async def search_tickets_smart(
        self,
        query: str,
        include_closed: bool = False,
        limit: int = 10,
    ) -> Dict[str, Any]:
        like = f"%{query}%"
        stmt = select(VTicketMasterExpanded).filter(
            VTicketMasterExpanded.Subject.ilike(like)
            | VTicketMasterExpanded.Ticket_Body.ilike(like)
        )
        if not include_closed:
            stmt = stmt.join(
                TicketStatusModel,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatusModel.ID,
                isouter=True,
            ).filter(~TicketStatusModel.Label.ilike("%closed%"))
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        tickets = result.scalars().all()
        search_results: List[TicketSearchResult] = []
        for ticket in tickets:
            search_results.append(
                TicketSearchResult(
                    ticket_id=ticket.Ticket_ID,
                    subject=ticket.Subject,
                    summary=(ticket.Ticket_Body[:200] + "...")
                    if ticket.Ticket_Body and len(ticket.Ticket_Body) > 200
                    else ticket.Ticket_Body,
                    status=ticket.Ticket_Status_Label or "Unknown",
                    priority=ticket.Priority_Level or "Medium",
                    assigned_to=ticket.Assigned_Name,
                    created_date=ticket.Created_Date.isoformat() if ticket.Created_Date else "",
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
        ticket = Ticket(
            Subject=title,
            Ticket_Body=description,
            Ticket_Contact_Name=contact.get("name"),
            Ticket_Contact_Email=contact.get("email"),
            Created_Date=datetime.now(timezone.utc),
            Ticket_Status_ID=1,
        )
        db_ticket = await TicketManager().create_ticket(self.db, ticket)
        return db_ticket


__all__ = [
    "TicketManager",
    "TicketTools",
    "TicketPriority",
    "TicketStatus",
    "TicketSearchResult",
]
