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

from .system_utilities import OperationResult, parse_search_datetime
from src.shared.utils.date_format import format_db_datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Semantic Filtering helpers (moved from enhanced_mcp_server)
# ---------------------------------------------------------------------------
# Mapping of friendly status terms to their corresponding Ticket_Status_ID values
# These mappings allow semantic filtering when searching or updating tickets.

# Closed states currently map to the single "Closed" status
# Defined before _STATUS_MAP so the mapping can reference it
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

_OPEN_STATE_IDS = [1, 2, 4, 5, 6, 8]
_CLOSED_STATE_IDS = [3]

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
    """Backward-compatible wrapper for :func:`apply_semantic_filters`."""
    return apply_semantic_filters(filters)


class TicketManager:
    """Handles all ticket CRUD and related operations."""

    # ------------------------------------------------------------------
    # Basic CRUD
    # ------------------------------------------------------------------
    async def get_ticket(
        self, db: AsyncSession, ticket_id: int
    ) -> VTicketMasterExpanded | None:
        return await db.get(VTicketMasterExpanded, ticket_id)

    async def create_ticket(
        self, db: AsyncSession, ticket_obj: Ticket | Dict[str, Any]
    ) -> OperationResult[Ticket]:
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
        if isinstance(updates, BaseModel):
            updates = updates.model_dump(exclude_unset=True)

        # Remove fields that should never be user-modifiable
        protected_fields = {"Ticket_ID", "Created_Date"}
        updates = {k: v for k, v in updates.items() if k not in protected_fields}

        if not updates:
            return None

        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None

        original_values: Dict[str, Any] = {}
        actual_changes: Dict[str, Dict[str, Any]] = {}

        for key, value in updates.items():
            if not hasattr(ticket, key):
                continue

            original_value = getattr(ticket, key)
            original_values[key] = original_value

            valid = await self._validate_field_update(
                db, ticket, key, value, original_value
            )
            if not valid:
                continue

            if original_value != value:
                actual_changes[key] = {"from": original_value, "to": value}
                setattr(ticket, key, value)

        if actual_changes:
            ticket.LastModified = datetime.now(timezone.utc)
            ticket.LastModfiedBy = "Gil AI"  # TODO: pass real user context

            try:
                await db.flush()
                await db.refresh(ticket)
                logger.info(
                    f"Updated ticket {ticket_id}: {list(actual_changes.keys())}"
                )
                return ticket
            except Exception:
                await db.rollback()
                logger.exception(f"Failed to update ticket {ticket_id}")
                raise
        else:
            logger.info(f"No changes applied to ticket {ticket_id}")
            return ticket

    async def _validate_field_update(
        self, db: AsyncSession, ticket: Ticket, field: str, new_value: Any, old_value: Any
    ) -> bool:
        """Validate and sanitize field updates according to business rules."""

        if isinstance(new_value, str) and field in ["Subject", "Ticket_Body", "Resolution"]:
            new_value = self._sanitize_text_input(new_value)
            setattr(ticket, field, new_value)

        if field == "Ticket_Status_ID":
            if not await self._validate_status_transition(db, old_value, new_value):
                logger.warning(f"Invalid status transition: {old_value} -> {new_value}")
                return False

            if new_value == 3 and not ticket.Resolution:
                logger.warning(f"Cannot close ticket {ticket.Ticket_ID} without resolution")
                return False

        if field == "Site_ID" and new_value is not None:
            if not await self._validate_site_exists(db, new_value):
                logger.warning(f"Site ID {new_value} does not exist")
                return False

        if field == "Asset_ID" and new_value is not None:
            if not await self._validate_asset_exists(db, new_value):
                logger.warning(f"Asset ID {new_value} does not exist")
                return False

        if field == "Severity_ID" and new_value is not None:
            if new_value not in [1, 2, 3, 4]:
                logger.warning(f"Invalid severity ID: {new_value}")
                return False

        if field in ["Ticket_Contact_Email", "Assigned_Email"] and new_value:
            if not self._validate_email_format(new_value):
                logger.warning(f"Invalid email format: {new_value}")
                return False

        if isinstance(new_value, str):
            if field in ["Subject"] and len(new_value) > 255:
                logger.warning(f"Subject too long: {len(new_value)} chars")
                return False
            if len(new_value) > 10000:
                logger.warning(f"Field {field} too long: {len(new_value)} chars")
                return False

        return True

    async def _validate_status_transition(
        self, db: AsyncSession, old_status: int, new_status: int
    ) -> bool:
        if new_status not in [1, 2, 3, 4, 5, 6, 8]:
            return False
        if old_status == 3 and new_status != 3:
            return False
        return True

    async def _validate_site_exists(self, db: AsyncSession, site_id: int) -> bool:
        from src.core.repositories.models import Site
        result = await db.get(Site, site_id)
        return result is not None

    async def _validate_asset_exists(self, db: AsyncSession, asset_id: int) -> bool:
        from src.core.repositories.models import Asset
        result = await db.get(Asset, asset_id)
        return result is not None

    def _validate_email_format(self, email: str) -> bool:
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

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

    def _sanitize_text_input(self, text: str) -> str:
        """Sanitize text input to prevent XSS and other issues."""
        if not isinstance(text, str):
            return str(text)

        import html as _html
        import re

        # HTML escape
        text = _html.escape(text)

        # Remove potentially dangerous characters
        text = re.sub(r'[<>"\']', '', text)

        # Normalize whitespace
        text = ' '.join(text.split())

        # Truncate if too long
        if len(text) > 10000:
            text = text[:10000] + "... [truncated]"

        return text

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

        if sanitized:
            escaped = self._escape_like_pattern(sanitized)
            like = f"%{escaped}%"
            stmt = stmt.filter(
                or_(
                    VTicketMasterExpanded.Subject.ilike(like, escape="\\"),
                    VTicketMasterExpanded.Ticket_Body.ilike(like, escape="\\"),
                )
            )

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

        filters_dict = params.model_dump(exclude_none=True) if params else {}
        sort_value = filters_dict.pop("sort", None)
        param_after = filters_dict.pop("created_after", None)
        param_before = filters_dict.pop("created_before", None)

        if created_after is None:
            created_after = param_after
        if created_before is None:
            created_before = param_before

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

        for key, value in filters_dict.items():
            if hasattr(VTicketMasterExpanded, key):
                col = getattr(VTicketMasterExpanded, key)
                if isinstance(value, list):
                    stmt = stmt.filter(col.in_(value))
                else:
                    stmt = stmt.filter(col == value)

        if created_after:
            created_after_dt = parse_search_datetime(created_after)
            stmt = stmt.filter(VTicketMasterExpanded.Created_Date >= created_after_dt)
        elif days is not None and days >= 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff = parse_search_datetime(cutoff)
            stmt = stmt.filter(VTicketMasterExpanded.Created_Date >= cutoff)

        if created_before:
            created_before_dt = parse_search_datetime(created_before)
            stmt = stmt.filter(VTicketMasterExpanded.Created_Date <= created_before_dt)

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

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = await db.scalar(count_stmt) or 0

        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)

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
            s = status.lower()
            if s == "open":

                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(_OPEN_STATE_IDS)
                )
            elif s == "closed":

                query = query.filter(VTicketMasterExpanded.Ticket_Status_ID.in_([3, 7]))

            elif s in {"in_progress", "progress"}:
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(
                        _STATUS_MAP["in_progress"]
                    )
                )

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
        query = select(VTicketMasterExpanded)
        if status:
            s = status.lower()
            if s == "open":

                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(_OPEN_STATE_IDS)
                )
            elif s == "closed":

                query = query.filter(VTicketMasterExpanded.Ticket_Status_ID.in_([3, 7]))
            elif s in {"in_progress", "progress"}:
                query = query.filter(
                    VTicketMasterExpanded.Ticket_Status_ID.in_(
                        _STATUS_MAP["in_progress"]
                    )
                )

        if days is not None and days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff = parse_search_datetime(cutoff)
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
        message = self._sanitize_text_input(message)

        msg = TicketMessage(
            Ticket_ID=ticket_id,
            Message=message,
            SenderUserCode=sender_code or "system",
            SenderUserName=sender_name or "System",
            DateTimeStamp=datetime.now(timezone.utc),
        )
        db.add(msg)
        try:
            await db.flush()
            await db.refresh(msg)
            logger.info("Posted message to ticket %s", ticket_id)
            return msg
        except SQLAlchemyError as e:
            logger.exception("Failed to save ticket message for %s", ticket_id)
            raise DatabaseError("Failed to save message", details=str(e))

    async def get_attachments(
        self, db: AsyncSession, ticket_id: int
    ) -> List[TicketAttachment]:
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
            ).filter(~TicketStatusModel.ID.in_(_CLOSED_STATE_IDS))
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        tickets = result.scalars().all()
        search_results: List[TicketSearchResult] = []
        for ticket in tickets:
            search_results.append(
                TicketSearchResult(
                    ticket_id=ticket.Ticket_ID,
                    subject=ticket.Subject,
                    summary=(
                        (ticket.Ticket_Body[:200] + "...")
                        if ticket.Ticket_Body and len(ticket.Ticket_Body) > 200
                        else ticket.Ticket_Body
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
    "_OPEN_STATE_IDS",
    "_CLOSED_STATE_IDS",
]
