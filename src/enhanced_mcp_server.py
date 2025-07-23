"""Configuration management for the MCP server and stub MCP server helpers."""

from __future__ import annotations

import json
import os
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import anyio
import html
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from sqlalchemy import select, func, or_

from .mcp_server import Tool
from src.infrastructure import database as db
from src.core.services.ticket_management import TicketManager
from src.core.services.reference_data import ReferenceDataManager
from src.shared.schemas.ticket import TicketExpandedOut, TicketCreate
from src.core.repositories.models import (
    Priority,
    Ticket,
    TicketStatus,
    VTicketMasterExpanded,
    Asset,
    Site,
    Vendor,
)
from src.core.services.analytics_reporting import (
    open_tickets_by_site,
    open_tickets_by_user,
    tickets_by_status,
    ticket_trend,
    sla_breaches,
    AnalyticsManager,
)
from src.core.services.enhanced_context import EnhancedContextManager
from src.core.services.advanced_query import AdvancedQueryManager
from src.shared.schemas.agent_data import AdvancedQuery

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration Classes
# ---------------------------------------------------------------------------

@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    max_retries: int = 3
    retry_base_delay: float = 0.1
    retry_backoff_factor: int = 2
    session_timeout: int = 300  # seconds
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True


@dataclass
class ServerConfig:
    """Main server configuration."""
    name: str = "helpdesk-ai-agent"
    version: str = "1.0.0"
    default_limit: int = 10
    max_limit: int = 1000
    enable_metrics: bool = True
    enable_health_check: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class SecurityConfig:
    """Security and validation configuration."""
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 100
    max_requests_per_hour: int = 1000
    require_authentication: bool = False
    allowed_origins: List[str] = field(default_factory=list)


@dataclass
class MCPServerConfig:
    """Complete MCP server configuration."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    @classmethod
    def from_env(cls) -> 'MCPServerConfig':
        """Create configuration from environment variables."""
        config = cls()
        
        # Database settings
        config.database.max_retries = int(os.getenv('DB_MAX_RETRIES', str(config.database.max_retries)))
        config.database.retry_base_delay = float(os.getenv('DB_RETRY_DELAY', str(config.database.retry_base_delay)))
        config.database.session_timeout = int(os.getenv('DB_SESSION_TIMEOUT', str(config.database.session_timeout)))
        config.database.pool_size = int(os.getenv('DB_POOL_SIZE', str(config.database.pool_size)))
        
        # Server settings
        config.server.name = os.getenv('SERVER_NAME', config.server.name)
        config.server.default_limit = int(os.getenv('DEFAULT_LIMIT', str(config.server.default_limit)))
        config.server.max_limit = int(os.getenv('MAX_LIMIT', str(config.server.max_limit)))
        config.server.enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
        
        # Logging settings
        config.logging.level = os.getenv('LOG_LEVEL', config.logging.level)
        config.logging.file_path = os.getenv('LOG_FILE_PATH')
        
        # Security settings
        config.security.enable_rate_limiting = os.getenv('ENABLE_RATE_LIMITING', 'true').lower() == 'true'
        config.security.max_requests_per_minute = int(os.getenv('MAX_REQUESTS_PER_MINUTE', str(config.security.max_requests_per_minute)))
        config.security.require_authentication = os.getenv('REQUIRE_AUTH', 'false').lower() == 'true'
        
        allowed_origins = os.getenv('ALLOWED_ORIGINS', '')
        if allowed_origins:
            config.security.allowed_origins = [origin.strip() for origin in allowed_origins.split(',')]
        
        return config
    
    def validate(self) -> None:
        """Validate configuration settings."""
        if self.server.max_limit <= 0:
            raise ValueError("max_limit must be positive")
        
        if self.server.default_limit <= 0:
            raise ValueError("default_limit must be positive")
        
        if self.server.default_limit > self.server.max_limit:
            raise ValueError("default_limit cannot exceed max_limit")
        
        if self.database.max_retries <= 0:
            raise ValueError("max_retries must be positive")
        
        if self.database.retry_base_delay <= 0:
            raise ValueError("retry_base_delay must be positive")
        
        if self.logging.level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            raise ValueError(f"Invalid log level: {self.logging.level}")


# Global configuration instance
_config: Optional[MCPServerConfig] = None


def get_config() -> MCPServerConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = MCPServerConfig.from_env()
        _config.validate()
    return _config


def set_config(config: MCPServerConfig) -> None:
    """Set the global configuration instance."""
    global _config
    config.validate()
    _config = config


# ---------------------------------------------------------------------------
# Semantic Filtering and Mapping
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "open": 1,
    "closed": 4,
    "resolved": 4,
    "in_progress": 2,
    "progress": 2,
    "pending": 3,
}

# IDs that represent an "open" style status in the database. When filtering on
# ``status=open`` these should all be matched.
_OPEN_STATE_IDS = [1, 2, 4, 5, 6, 8]

_PRIORITY_MAP = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def _format_ticket_by_level(ticket: Any) -> dict:
    """Return a dict representation of a ticket with consistent priority labeling."""
    if isinstance(ticket, dict):
        data = ticket.copy()
    else:
        data = TicketExpandedOut.model_validate(ticket).model_dump()

    level = data.get("Priority_Level")
    if level and isinstance(level, str):
        data["Priority_Level"] = level.capitalize()

    return data


def _calculate_search_relevance(ticket: dict, query: str) -> float:
    """Calculate relevance score based on query matches."""
    if not query:
        return 0.0
        
    q = query.lower()
    words = q.split()
    
    subject = (ticket.get("Subject") or "").lower()
    body = (ticket.get("body_preview") or "").lower()
    category = (ticket.get("Category_Name") or "").lower()

    score = 0.0
    
    # Exact matches get highest scores
    if q in subject:
        score += 3.0
    if q in body:
        score += 2.0
    if q in category:
        score += 1.5
    
    # Word matches get lower scores
    for word in words:
        if len(word) > 2:  # Skip very short words
            if word in subject:
                score += 1.0
            if word in body:
                score += 0.5
            if word in category:
                score += 0.3

    return score


def _generate_search_highlights(ticket: dict, query: str) -> dict:
    """Highlight query terms in the subject and body preview."""
    if not query:
        return {"subject": ticket.get("Subject", ""), "body": ticket.get("body_preview", "")}
        
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    subject = ticket.get("Subject") or ""
    body = ticket.get("body_preview") or ""
    
    return {
        "subject": pattern.sub(lambda m: f"<em>{m.group()}</em>", subject),
        "body": pattern.sub(lambda m: f"<em>{m.group()}</em>", body),
    }


def _apply_semantic_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Translate human-friendly filters into database column filters."""
    if not filters:
        return {}
        
    translated: dict[str, Any] = {}
    
    for key, value in filters.items():
        k = key.lower()
        
        if k in {"status", "ticket_status"}:
            if isinstance(value, str):
                v = value.lower()
                if v == "open":
                    translated["Ticket_Status_ID"] = _OPEN_STATE_IDS
                else:
                    translated["Ticket_Status_ID"] = _STATUS_MAP.get(v, value)
            elif isinstance(value, list):
                ids: list[Any] = []
                for item in value:
                    if isinstance(item, str) and item.lower() == "open":
                        ids.extend(_OPEN_STATE_IDS)
                    elif isinstance(item, str):
                        ids.append(_STATUS_MAP.get(item.lower(), item))
                    else:
                        ids.append(item)
                translated["Ticket_Status_ID"] = ids
            else:
                translated["Ticket_Status_ID"] = value
                
        elif k in {"priority", "priority_level"}:
            if isinstance(value, str):
                mapped_priority = _PRIORITY_MAP.get(value.lower())
                if mapped_priority:
                    translated["Priority_Level"] = mapped_priority
                else:
                    translated["Priority_Level"] = value
            else:
                translated["Severity_ID"] = value
                
        elif k == "assignee":
            translated["Assigned_Email"] = value
            
        elif k == "category":
            translated["Ticket_Category_ID"] = value
            
        else:
            # Pass through other filters unchanged
            translated[key] = value
            
    return translated


# ---------------------------------------------------------------------------
# MCP Server Tool Implementations
# ---------------------------------------------------------------------------

async def _get_ticket(ticket_id: int, include_full_context: bool = False) -> Dict[str, Any]:
    """Retrieve a ticket by ID and return full details.

    If ``include_full_context`` is true, the response also contains the last few
    messages, attachments and a short user ticket history for additional
    context.
    """
    try:
        async with db.SessionLocal() as db_session:
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            if not ticket:
                return {"status": "error", "error": f"Ticket {ticket_id} not found"}
            data = _format_ticket_by_level(ticket)

            if include_full_context:
                mgr = EnhancedContextManager(db_session)
                messages = await mgr._get_ticket_messages(ticket_id)
                attachments = await mgr._get_ticket_attachments(ticket_id)
                history = await mgr._get_user_ticket_history(
                    ticket.Ticket_Contact_Email,
                    limit=5,
                )
                return {
                    "status": "success",
                    "data": data,
                    "messages": messages[-5:],
                    "attachments": attachments[-5:],
                    "user_history": history,
                }

            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _list_tickets(
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """List tickets using semantic filters and return serialized results."""
    try:
        async with db.SessionLocal() as db_session:
            # Apply semantic filtering
            applied_filters = _apply_semantic_filters(filters or {})
            
            tickets = await TicketManager().list_tickets(
                db_session,
                filters=applied_filters,
                skip=skip,
                limit=limit,
                sort=sort,
            )
            
            data = [_format_ticket_by_level(t) for t in tickets]
            
            return {
                "status": "success", 
                "data": data,
                "count": len(data),
                "skip": skip,
                "limit": limit
            }
    except Exception as e:
        logger.error(f"Error in list_tickets: {e}")
        return {"status": "error", "error": str(e)}


async def _get_tickets_by_user(
    identifier: str,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    filters: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return tickets associated with a user."""
    try:
        async with db.SessionLocal() as db_session:
            # Apply semantic filters
            applied_filters = _apply_semantic_filters(filters or {})
            
            tickets = await TicketManager().get_tickets_by_user(
                db_session,
                identifier,
                skip=skip,
                limit=limit,
                status=status,
                filters=applied_filters,
            )
            
            data = [_format_ticket_by_level(t) for t in tickets]
            
            return {
                "status": "success",
                "data": data,
                "user": identifier,
                "count": len(data)
            }
    except Exception as e:
        logger.error(f"Error in get_tickets_by_user: {e}")
        return {"status": "error", "error": str(e)}


async def _search_tickets(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search tickets and return results scored by relevance."""
    try:
        async with db.SessionLocal() as db_session:
            results = await TicketManager().search_tickets(
                db_session, query, limit=limit * 2  # Get more results for relevance sorting
            )
            
            enriched = []
            for r in results:
                score = _calculate_search_relevance(r, query)
                if score > 0:  # Only include results with some relevance
                    highlights = _generate_search_highlights(r, query)
                    r = _format_ticket_by_level(r)
                    r["relevance"] = round(score, 2)
                    r["highlights"] = highlights
                    enriched.append(r)

            # Sort by relevance and limit results
            enriched.sort(key=lambda d: d["relevance"], reverse=True)
            enriched = enriched[:limit]
            
            return {
                "status": "success",
                "data": enriched,
                "query": query,
                "count": len(enriched)
            }
    except Exception as e:
        logger.error(f"Error in search_tickets: {e}")
        return {"status": "error", "error": str(e)}


async def _search_tickets_unified(
    text: str | None = None,
    user: str | None = None,
    days: int | None = None,
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """Unified ticket search supporting text, user and timeframe filters."""
    try:
        async with db.SessionLocal() as db_session:
            base_stmt = select(VTicketMasterExpanded)

            if text:
                sanitized = html.escape(text)
                pattern = f"%{sanitized}%"
                base_stmt = base_stmt.filter(
                    or_(
                        VTicketMasterExpanded.Subject.ilike(pattern),
                        VTicketMasterExpanded.Ticket_Body.ilike(pattern),
                    )
                )

            if user:
                ident = user.lower()
                base_stmt = base_stmt.filter(
                    or_(
                        func.lower(VTicketMasterExpanded.Ticket_Contact_Name) == ident,
                        func.lower(VTicketMasterExpanded.Ticket_Contact_Email) == ident,
                        func.lower(VTicketMasterExpanded.Assigned_Name) == ident,
                        func.lower(VTicketMasterExpanded.Assigned_Email) == ident,
                    )
                )

            if days is not None and days >= 0:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                base_stmt = base_stmt.filter(VTicketMasterExpanded.Created_Date >= cutoff)

            if filters:
                applied = _apply_semantic_filters(filters)
                for key, value in applied.items():
                    if hasattr(VTicketMasterExpanded, key):
                        col = getattr(VTicketMasterExpanded, key)
                        if isinstance(value, list):
                            base_stmt = base_stmt.filter(col.in_(value))
                        else:
                            base_stmt = base_stmt.filter(col == value)

            # Sorting
            order_stmt = base_stmt
            if sort:
                for key in reversed(sort):
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
                        order_stmt = order_stmt.order_by(
                            attr.desc() if direction == "desc" else attr.asc()
                        )
            else:
                order_stmt = order_stmt.order_by(VTicketMasterExpanded.Created_Date.desc())

            count_stmt = select(func.count()).select_from(order_stmt.subquery())
            total_count = await db_session.scalar(count_stmt) or 0

            if skip:
                order_stmt = order_stmt.offset(skip)
            if limit:
                order_stmt = order_stmt.limit(limit)

            result = await db_session.execute(order_stmt)
            records = result.scalars().all()

            data = []
            for r in records:
                item = _format_ticket_by_level(r)
                if text:
                    score = _calculate_search_relevance(item, text)
                    item["relevance"] = round(score, 2)
                    item["highlights"] = _generate_search_highlights(item, text)
                data.append(item)

            if text:
                data.sort(key=lambda d: d.get("relevance", 0), reverse=True)

            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "total_count": total_count,
                "skip": skip,
                "limit": limit,
            }
    except Exception as e:
        logger.error(f"Error in search_tickets_unified: {e}")
        return {"status": "error", "error": str(e)}


async def _search_tickets_advanced(**criteria: Any) -> Dict[str, Any]:
    """Perform advanced ticket search with metadata."""
    try:
        # Validate and sanitize input
        query = AdvancedQuery.model_validate(criteria or {})

        # Sanitize string inputs to prevent XSS
        if query.text_search:
            query.text_search = html.escape(query.text_search)
        if query.contact_name:
            query.contact_name = html.escape(query.contact_name)

        query.search_fields = [html.escape(f) for f in query.search_fields]

        # Sanitize custom filters
        sanitized_custom: Dict[str, Any] = {}
        for key, val in query.custom_filters.items():
            sanitized_custom[key] = html.escape(val) if isinstance(val, str) else val
        query.custom_filters = sanitized_custom

        # Sanitize list fields
        if query.assigned_to:
            query.assigned_to = [html.escape(v) for v in query.assigned_to]
        if query.contact_email:
            query.contact_email = [html.escape(v) for v in query.contact_email]
        if query.status_filter:
            query.status_filter = [html.escape(str(v)) for v in query.status_filter]

        async with db.SessionLocal() as db_session:
            mgr = AdvancedQueryManager(db_session)
            result = await mgr.query_tickets_advanced(query)
            return {"status": "success", "data": result.model_dump()}
            
    except Exception as e:
        logger.error(f"Error in search_tickets_advanced: {e}")
        return {"status": "error", "error": str(e)}


async def _create_ticket(**payload: Any) -> Dict[str, Any]:
    """Create a new ticket and return the created record."""
    try:
        async with db.SessionLocal() as db_session:
            # Set default timestamps
            now = datetime.now(timezone.utc)
            payload.setdefault("Created_Date", now)
            payload.setdefault("LastModified", now)
            
            result = await TicketManager().create_ticket(db_session, payload)
            if not result.success:
                await db_session.rollback()
                raise Exception(result.error or "Failed to create ticket")
                
            await db_session.commit()
            
            # Fetch the created ticket with all details
            ticket = await TicketManager().get_ticket(
                db_session, result.data.Ticket_ID
            )
            data = _format_ticket_by_level(ticket)
            
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in create_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _update_ticket(ticket_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing ticket."""
    try:
        async with db.SessionLocal() as db_session:
            # Apply semantic filters to updates
            applied_updates = _apply_semantic_filters(updates)
            message = applied_updates.pop("message", None)

            # Closing logic
            if applied_updates.get("Ticket_Status_ID") == 4 and "Closed_Date" not in applied_updates:
                applied_updates["Closed_Date"] = datetime.now(timezone.utc)

            # Assignment defaults
            if "Assigned_Email" in applied_updates and "Assigned_Name" not in applied_updates:
                applied_updates["Assigned_Name"] = applied_updates.get("Assigned_Email")

            applied_updates["LastModified"] = datetime.now(timezone.utc)
            applied_updates["LastModifiedBy"] = "Gil AI"

            updated = await TicketManager().update_ticket(db_session, ticket_id, applied_updates)
            if not updated:
                await db_session.rollback()
                return {"status": "error", "error": f"Ticket {ticket_id} not found"}

            if message:
                await TicketManager().post_message(
                    db_session,
                    ticket_id,
                    message,
                    applied_updates.get("Assigned_Email", "system"),
                    applied_updates.get("Assigned_Name", applied_updates.get("Assigned_Email", "system")),
                )

            await db_session.commit()

            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = _format_ticket_by_level(ticket)

            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in update_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _bulk_update_tickets(
    ticket_ids: list[int],
    updates: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Apply the same updates to multiple tickets."""
    try:
        if not ticket_ids:
            return {"status": "error", "error": "No ticket IDs provided"}
        if not updates:
            return {"status": "error", "error": "No updates provided"}
        async with db.SessionLocal() as db_session:
            mgr = TicketManager()
            applied_updates = _apply_semantic_filters(updates)
            applied_updates["LastModified"] = datetime.now(timezone.utc)
            applied_updates["LastModifiedBy"] = "Gil AI"
            
            updated: list[Dict[str, Any]] = []
            failed: list[Dict[str, Any]] = []
            
            for tid in ticket_ids:
                try:
                    result = await mgr.update_ticket(db_session, tid, applied_updates)
                    if result:
                        ticket = await mgr.get_ticket(db_session, tid)
                        updated.append(_format_ticket_by_level(ticket))
                    else:
                        failed.append({"ticket_id": tid, "error": "Not found"})
                except Exception as e:
                    failed.append({"ticket_id": tid, "error": str(e)})

            if dry_run:
                await db_session.rollback()
            else:
                await db_session.commit()

            return {
                "status": "success",
                "updated": updated,
                "failed": failed,
                "dry_run": dry_run,
                "total_processed": len(ticket_ids),
                "total_updated": len(updated),
                "total_failed": len(failed)
            }
    except Exception as e:
        logger.error(f"Error in bulk_update_tickets: {e}")
        return {"status": "error", "error": str(e)}


async def _add_ticket_message(
    ticket_id: int,
    message: str,
    sender_name: str,
    sender_code: str | None = None,
) -> Dict[str, Any]:
    """Add a message to a ticket."""
    try:
        async with db.SessionLocal() as db_session:
            created = await TicketManager().post_message(
                db_session,
                ticket_id,
                message,
                sender_code or sender_name,
                sender_name,
            )
            
            await db_session.commit()
            
            return {
                "status": "success",
                "data": {
                    "id": created.ID,
                    "ticket_id": created.Ticket_ID,
                    "message": created.Message,
                    "sender_name": created.SenderUserName,
                    "timestamp": created.DateTimeStamp.isoformat() if created.DateTimeStamp else None
                },
            }
    except Exception as e:
        logger.error(f"Error in add_ticket_message: {e}")
        return {"status": "error", "error": str(e)}




async def _get_ticket_messages(ticket_id: int) -> Dict[str, Any]:
    """Return messages for a ticket with additional metadata."""
    try:
        async with db.SessionLocal() as db_session:
            msgs = await TicketManager().get_messages(db_session, ticket_id)
            
            data = [
                {
                    "ID": m.ID,
                    "Ticket_ID": m.Ticket_ID,
                    "Message": m.Message,
                    "SenderUserCode": m.SenderUserCode,
                    "SenderUserName": m.SenderUserName,
                    "DateTimeStamp": m.DateTimeStamp.isoformat() if m.DateTimeStamp else None,
                    "message_length": len(m.Message or ""),
                }
                for m in msgs
            ]
            
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "ticket_id": ticket_id
            }
    except Exception as e:
        logger.error(f"Error in get_ticket_messages: {e}")
        return {"status": "error", "error": str(e)}


async def _get_ticket_attachments(ticket_id: int) -> Dict[str, Any]:
    """Return attachments for a ticket with file metadata."""
    try:
        async with db.SessionLocal() as db_session:
            atts = await TicketManager().get_attachments(db_session, ticket_id)
            
            data = [
                {
                    "ID": a.ID,
                    "Ticket_ID": a.Ticket_ID,
                    "Name": a.Name,
                    "WebURL": a.WebURl,  # Note: keeping original field name
                    "UploadDateTime": a.UploadDateTime.isoformat() if a.UploadDateTime else None,
                    "file_type": os.path.splitext(a.Name)[1].lstrip(".").lower() if a.Name else "unknown",
                    "file_name_without_extension": os.path.splitext(a.Name)[0] if a.Name else ""
                }
                for a in atts
            ]
            
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "ticket_id": ticket_id
            }
    except Exception as e:
        logger.error(f"Error in get_ticket_attachments: {e}")
        return {"status": "error", "error": str(e)}


async def _get_open_tickets(
    days: int = 3650,
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """Return open tickets with optional filters and sorting."""
    try:
        async with db.SessionLocal() as db_session:
            # Get tickets within timeframe
            tickets = await TicketManager().get_tickets_by_timeframe(
                db_session,
                status="open",
                days=days,
                limit=(limit + skip) * 2 if limit else None,  # Get extra for filtering
            )

            # Apply additional filters
            if filters:
                applied_filters = _apply_semantic_filters(filters)
                filtered = []
                for t in tickets:
                    match = True
                    for k, v in applied_filters.items():
                        if hasattr(t, k) and getattr(t, k) != v:
                            match = False
                            break
                    if match:
                        filtered.append(t)
                tickets = filtered

            # Apply sorting
            if sort:
                for key in reversed(sort):
                    direction = "asc"
                    column = key
                    
                    if key.startswith("-"):
                        column = key[1:]
                        direction = "desc"
                    elif " " in key:
                        column, dir_part = key.rsplit(" ", 1)
                        if dir_part.lower() in {"asc", "desc"}:
                            direction = dir_part.lower()
                            
                    if tickets and hasattr(tickets[0], column):
                        tickets.sort(
                            key=lambda t: getattr(t, column, None) or "",
                            reverse=direction == "desc",
                        )

            # Apply pagination
            total_count = len(tickets)
            if skip:
                tickets = tickets[skip:]
            if limit:
                tickets = tickets[:limit]

            data = [_format_ticket_by_level(t) for t in tickets]
            
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "total_count": total_count,
                "skip": skip,
                "limit": limit,
                "days": days
            }
    except Exception as e:
        logger.error(f"Error in get_open_tickets: {e}")
        return {"status": "error", "error": str(e)}


async def _get_analytics_unified(
    type: str, params: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Unified analytics endpoint supporting multiple report types."""
    try:
        params = params or {}

        if type == "overview":
            return await _system_snapshot()

        if type == "ticket_counts":
            return await _get_ticket_stats()

        if type == "workload":
            return await _get_workload_analytics()

        if type == "sla_performance":
            days = params.get("days", 30)
            return await _sla_metrics(days=days)

        if type == "trends":
            days = params.get("days", 7)
            async with db.SessionLocal() as db_session:
                trend = await ticket_trend(db_session, days)
            return {"status": "success", "data": trend, "days": days}

        if type == "overdue_tickets":
            async with db.SessionLocal() as db_session:
                mgr = EnhancedContextManager(db_session)
                overdue = await mgr._get_overdue_tickets_summary()
            return {"status": "success", "data": overdue}

        valid_types = [
            "overview",
            "ticket_counts",
            "workload",
            "sla_performance",
            "trends",
            "overdue_tickets",
        ]
        return {
            "status": "error",
            "error": f"Unknown analytics type: {type}. Valid types: {', '.join(valid_types)}",
        }
    except Exception as e:
        logger.error(f"Error in get_analytics_unified: {e}")
        return {"status": "error", "error": str(e)}


async def _get_sla_metrics(
    sla_days: int = 2,
    filters: Dict[str, Any] | None = None,
    status_ids: list[int] | None = None,
) -> Dict[str, Any]:
    """Return SLA compliance metrics."""
    try:
        async with db.SessionLocal() as db_session:
            # Count open tickets
            query = (
                select(func.count(Ticket.Ticket_ID))
                .join(TicketStatus, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
                .filter(
                    or_(
                        TicketStatus.Label.ilike("%open%"),
                        TicketStatus.Label.ilike("%progress%"),
                    )
                )
            )
            
            # Apply filters
            if filters:
                applied_filters = _apply_semantic_filters(filters)
                for key, value in applied_filters.items():
                    if hasattr(Ticket, key):
                        query = query.filter(getattr(Ticket, key) == value)

            open_count = await db_session.scalar(query) or 0

            # Get breach count
            breaches = await sla_breaches(
                db_session,
                sla_days=sla_days,
                filters=filters,
                status_ids=status_ids,
            )

            # Calculate compliance percentage
            compliance = ((open_count - breaches) / open_count * 100) if open_count > 0 else 100.0

            return {
                "status": "success",
                "data": {
                    "open_tickets": open_count,
                    "sla_breaches": breaches,
                    "sla_compliance_pct": round(compliance, 2),
                    "sla_days": sla_days,
                    "compliant_tickets": open_count - breaches,
                },
                "filters_applied": bool(filters),
                "status_ids": status_ids
            }
    except Exception as e:
        logger.error(f"Error in get_sla_metrics: {e}")
        return {"status": "error", "error": str(e)}


async def _get_reference_data_unified(
    type: str,
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
    include_counts: bool = False,
) -> Dict[str, Any]:
    """Return reference data records with optional ticket counts."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = ReferenceDataManager()

            records: list[Any]
            field = None
            if type == "sites":
                records = await mgr.list_sites(db_session, skip=skip, limit=limit, filters=filters, sort=sort)
                field = "Site_ID"
                ids = [r.ID for r in records]
                count_stmt = select(func.count(Site.ID))
                if filters:
                    for key, value in filters.items():
                        if hasattr(Site, key):
                            count_stmt = count_stmt.filter(getattr(Site, key) == value)
                total_count = await db_session.scalar(count_stmt) or 0
            elif type == "assets":
                records = await mgr.list_assets(db_session, skip=skip, limit=limit, filters=filters, sort=sort)
                field = "Asset_ID"
                ids = [r.ID for r in records]
                count_stmt = select(func.count(Asset.ID))
                if filters:
                    for key, value in filters.items():
                        if hasattr(Asset, key):
                            count_stmt = count_stmt.filter(getattr(Asset, key) == value)
                total_count = await db_session.scalar(count_stmt) or 0
            elif type == "vendors":
                records = await mgr.list_vendors(db_session, skip=skip, limit=limit, filters=filters, sort=sort)
                field = "Assigned_Vendor_ID"
                ids = [r.ID for r in records]
                count_stmt = select(func.count(Vendor.ID))
                if filters:
                    for key, value in filters.items():
                        if hasattr(Vendor, key):
                            count_stmt = count_stmt.filter(getattr(Vendor, key) == value)
                total_count = await db_session.scalar(count_stmt) or 0
            elif type == "categories":
                records = await mgr.list_categories(db_session, filters=filters, sort=sort)
                total_count = len(records)
                if skip:
                    records = records[skip:]
                if limit:
                    records = records[:limit]
                field = "Ticket_Category_ID"
                ids = [r.ID for r in records]
            elif type == "priorities":
                result = await db_session.execute(select(Priority).order_by(Priority.ID))
                records = result.scalars().all()
                total_count = len(records)
                if skip:
                    records = records[skip:]
                if limit:
                    records = records[:limit]
                field = "Priority_Level"
                ids = [r.Level for r in records]
            elif type == "statuses":
                result = await db_session.execute(select(TicketStatus).order_by(TicketStatus.ID))
                records = result.scalars().all()
                total_count = len(records)
                if skip:
                    records = records[skip:]
                if limit:
                    records = records[:limit]
                field = "Ticket_Status_ID"
                ids = [r.ID for r in records]
            else:
                return {"status": "error", "error": f"Unknown reference data type: {type}"}

            if include_counts and field:
                open_counts = await _count_open_tickets_by_field(db_session, field, ids)
                total_counts = await _count_total_tickets_by_field(db_session, field, ids)
            else:
                open_counts = {}
                total_counts = {}

            data = []
            for r in records:
                item = r.__dict__.copy()
                item.pop("_sa_instance_state", None)
                if type == "priorities":
                    item = {
                        "id": r.ID,
                        "level": r.Level,
                        "semantic_name": _PRIORITY_MAP.get(r.Level.lower(), r.Level) if r.Level else None,
                    }
                    key = r.Level
                else:
                    key = r.ID

                if include_counts:
                    item["open_tickets"] = open_counts.get(key, 0)
                    item["total_tickets"] = total_counts.get(key, 0)
                    item["closed_tickets"] = item["total_tickets"] - item["open_tickets"]

                data.append(item)

            result_obj = {
                "status": "success",
                "data": data,
                "type": type,
                "count": len(data),
                "skip": skip,
                "limit": limit,
                "total_count": total_count,
            }

            return result_obj
    except Exception as e:
        logger.error(f"Error in get_reference_data: {e}")
        return {"status": "error", "error": str(e)}


async def _count_open_tickets_by_field(
    db_session, field_name: str, ids: list[int]
) -> dict[int, int]:
    """Return open ticket counts grouped by the specified field."""
    if not ids:
        return {}
        
    if not hasattr(VTicketMasterExpanded, field_name):
        logger.warning(f"Field {field_name} not found in VTicketMasterExpanded")
        return {}
        
    column = getattr(VTicketMasterExpanded, field_name)
    
    result = await db_session.execute(
        select(column, func.count(VTicketMasterExpanded.Ticket_ID))
        .join(
            TicketStatus,
            VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
            isouter=True,
        )
        .filter(column.in_(ids))
        .filter(
            or_(
                TicketStatus.Label.ilike("%open%"),
                TicketStatus.Label.ilike("%progress%"),
            )
        )
        .group_by(column)
    )
    
    return {row[0]: row[1] for row in result.all()}


async def _count_total_tickets_by_field(
    db_session, field_name: str, ids: list[int]
) -> dict[int, int]:
    """Return total ticket counts grouped by a field."""
    if not ids:
        return {}
        
    if not hasattr(VTicketMasterExpanded, field_name):
        logger.warning(f"Field {field_name} not found in VTicketMasterExpanded")
        return {}
        
    column = getattr(VTicketMasterExpanded, field_name)
    
    result = await db_session.execute(
        select(column, func.count(VTicketMasterExpanded.Ticket_ID))
        .filter(column.in_(ids))
        .group_by(column)
    )
    
    return {row[0]: row[1] for row in result.all()}




async def _ticket_full_context(ticket_id: int) -> Dict[str, Any]:
    """Return extended context for a ticket."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = EnhancedContextManager(db_session)
            context = await mgr.get_ticket_full_context(ticket_id)
            
            return {
                "status": "success",
                "data": context,
                "ticket_id": ticket_id
            }
    except Exception as e:
        logger.error(f"Error in get_ticket_full_context: {e}")
        return {"status": "error", "error": str(e)}


async def _system_snapshot() -> Dict[str, Any]:
    """Return overall system snapshot."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = EnhancedContextManager(db_session)
            snapshot = await mgr.get_system_snapshot()
            
            return {
                "status": "success",
                "data": snapshot,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        logger.error(f"Error in get_system_snapshot: {e}")
        return {"status": "error", "error": str(e)}


async def _get_ticket_stats() -> Dict[str, Any]:
    """Return ticket statistics across multiple dimensions."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = EnhancedContextManager(db_session)
            
            data = {
                "by_status": await mgr._get_ticket_counts_by_status(),
                "by_priority": await mgr._get_ticket_counts_by_priority(),
                "by_site": await mgr._get_ticket_counts_by_site(),
                "by_category": await mgr._get_ticket_counts_by_category(),
                "summary": {
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Calculate totals
            total_tickets = sum(item["count"] for item in data["by_status"])
            open_tickets = sum(
                item["count"] for item in data["by_status"]
                if "open" in item["status"].lower() or "progress" in item["status"].lower()
            )
            
            data["summary"]["total_tickets"] = total_tickets
            data["summary"]["open_tickets"] = open_tickets
            data["summary"]["closed_tickets"] = total_tickets - open_tickets
            
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_ticket_stats: {e}")
        return {"status": "error", "error": str(e)}


async def _get_workload_analytics() -> Dict[str, Any]:
    """Return workload analytics for technicians and queues."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = EnhancedContextManager(db_session)
            
            data = {
                "technician_workloads": await mgr._get_all_technician_workloads(),
                "unassigned_tickets": await mgr._get_unassigned_tickets_summary(),
                "overdue_tickets": await mgr._get_overdue_tickets_summary(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Calculate summary statistics
            total_assigned = sum(
                w.get("open_tickets", 0) for w in data["technician_workloads"]
            )
            total_unassigned = data["unassigned_tickets"].get("total", 0)
            total_overdue = data["overdue_tickets"].get("total", 0)
            
            data["summary"] = {
                "total_open_tickets": total_assigned + total_unassigned,
                "total_assigned": total_assigned,
                "total_unassigned": total_unassigned,
                "total_overdue": total_overdue,
                "technicians_count": len(data["technician_workloads"])
            }
            
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_workload_analytics: {e}")
        return {"status": "error", "error": str(e)}


async def _advanced_search(**query: Any) -> Dict[str, Any]:
    """Run an advanced ticket search."""
    try:
        async with db.SessionLocal() as db_session:
            manager = AdvancedQueryManager(db_session)
            q = AdvancedQuery(**query)
            result = await manager.query_tickets_advanced(q)
            
            return {
                "status": "success",
                "data": result.model_dump(),
                "query": query
            }
    except Exception as e:
        logger.error(f"Error in advanced_search: {e}")
        return {"status": "error", "error": str(e)}


async def _sla_metrics(days: int = 30) -> Dict[str, Any]:
    """Retrieve comprehensive SLA metrics dashboard."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = AnalyticsManager(db_session)
            dashboard = await mgr.get_comprehensive_dashboard(time_range_days=days)
            
            return {
                "status": "success",
                "data": dashboard,
                "time_range_days": days,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        logger.error(f"Error in sla_metrics: {e}")
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------

ENHANCED_TOOLS: List[Tool] = [
    Tool(
        name="get_ticket",
        description="Get a ticket by ID with optional context",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID"},
                "include_full_context": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include recent messages and history",
                },
            },
            "required": ["ticket_id"],
            "examples": [
                {"ticket_id": 123},
                {"ticket_id": 123, "include_full_context": True},
            ],
        },
        _implementation=_get_ticket,
    ),
    Tool(
        name="create_ticket",
        description="Create a new ticket",
        inputSchema=TicketCreate.model_json_schema(),
        _implementation=_create_ticket,
    ),
    Tool(
        name="update_ticket",
        description="Update an existing ticket (supports semantic values)",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID to update"},
                "updates": {"type": "object", "description": "Fields to update (supports semantic values)"},
            },
            "required": ["ticket_id", "updates"],
            "examples": [
                {"ticket_id": 1, "updates": {"Subject": "Updated subject"}},
                {"ticket_id": 2, "updates": {"status": "closed", "priority": "high"}}
            ],
        },
        _implementation=_update_ticket,
    ),
    Tool(
        name="bulk_update_tickets",
        description="Update multiple tickets at once",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of ticket IDs"},
                "updates": {"type": "object", "description": "Fields to update on all tickets"},
                "dry_run": {"type": "boolean", "default": False, "description": "Preview changes without saving"},
            },
            "required": ["ticket_ids", "updates"],
            "examples": [
                {"ticket_ids": [1, 2, 3], "updates": {"status": "closed"}},
                {"ticket_ids": [4, 5], "updates": {"assignee": "tech@example.com"}, "dry_run": True}
            ],
        },
        _implementation=_bulk_update_tickets,
    ),
    Tool(
        name="add_ticket_message",
        description="Add a message/comment to a ticket",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID"},
                "message": {"type": "string", "description": "Message content"},
                "sender_name": {"type": "string", "description": "Sender's name"},
                "sender_code": {"type": "string", "description": "Sender's code/ID"},
            },
            "required": ["ticket_id", "message", "sender_name"],
            "examples": [
                {"ticket_id": 1, "message": "Working on this issue", "sender_name": "Tech Support"}
            ],
        },
        _implementation=_add_ticket_message,
    ),
    Tool(
        name="get_ticket_messages",
        description="Retrieve all messages for a ticket",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer", "description": "The ticket ID"}},
            "required": ["ticket_id"],
            "examples": [{"ticket_id": 123}],
        },
        _implementation=_get_ticket_messages,
    ),
    Tool(
        name="get_ticket_attachments",
        description="Retrieve all attachments for a ticket",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer", "description": "The ticket ID"}},
            "required": ["ticket_id"],
            "examples": [{"ticket_id": 123}],
        },
        _implementation=_get_ticket_attachments,
    ),
    Tool(
        name="search_tickets",
        description="Unified ticket search with text, user, timeframe and filters",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Search query text"},
                "user": {"type": "string", "description": "User email or name"},
                "days": {"type": "integer", "description": "Tickets from last N days", "default": 30},
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "examples": [
                {"text": "printer error", "days": 7},
                {"user": "tech@example.com", "filters": {"status": "open"}},
                {"text": "network", "user": "alice@example.com", "days": 30}
            ],
        },
        _implementation=_search_tickets_unified,
    ),
    Tool(
        name="get_analytics",
        description="Retrieve analytics reports",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["overview", "ticket_counts", "workload", "sla_performance", "trends", "overdue_tickets"],
                    "description": "Analytics report type"
                },
                "params": {"type": "object", "description": "Optional parameters for the report"},
            },
            "required": ["type"],
            "examples": [
                {"type": "overview"},
                {"type": "trends", "params": {"days": 7}},
                {"type": "sla_performance", "params": {"days": 30}}
            ],
        },
        _implementation=_get_analytics_unified,
    ),
    Tool(
        name="get_reference_data",
        description="Retrieve reference data with optional ticket counts",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": [
                        "sites",
                        "assets",
                        "vendors",
                        "categories",
                        "priorities",
                        "statuses",
                    ],
                    "description": "Type of reference data",
                },
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
                "include_counts": {"type": "boolean", "default": False},
            },
            "required": ["type"],
            "examples": [
                {"type": "sites", "include_counts": True},
                {"type": "priorities"},
            ],
        },
        _implementation=_get_reference_data_unified,
    ),
    Tool(
        name="get_ticket_full_context",
        description="Get comprehensive context for a ticket including related data",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer", "description": "The ticket ID"}},
            "required": ["ticket_id"],
            "examples": [{"ticket_id": 123}],
        },
        _implementation=_ticket_full_context,
    ),
    Tool(

        name="advanced_search",
        description="Run a detailed ticket search with advanced options",
        inputSchema={
            "type": "object",
            "properties": {
                "text_search": {"type": "string", "description": "Text to search for"},
                "search_fields": {"type": "array", "items": {"type": "string"}, "default": ["Subject", "Ticket_Body"]},
                "created_after": {"type": "string", "format": "date-time"},
                "created_before": {"type": "string", "format": "date-time"},
                "status_filter": {"type": "array", "items": {"type": "string"}},
                "priority_filter": {"type": "array", "items": {"type": "integer"}},
                "assigned_to": {"type": "array", "items": {"type": "string"}},
                "unassigned_only": {"type": "boolean", "default": False},
                "site_filter": {"type": "array", "items": {"type": "integer"}},
                "limit": {"type": "integer", "default": 100},
                "offset": {"type": "integer", "default": 0}
            },
            "examples": [
                {"text_search": "printer issue", "limit": 10},
                {"text_search": "network", "limit": 50, "offset": 20}
            ],
        },
        _implementation=_advanced_search,
    ),
    Tool(
        name="get_system_snapshot",
        description="Get current system overview and statistics",
        inputSchema={
            "type": "object",
            "properties": {},
            "examples": [{}],
        },
        _implementation=_system_snapshot,
    ),
    Tool(
        name="get_ticket_stats",
        description="Get ticket statistics grouped by status, priority, site, and category",
        inputSchema={
            "type": "object",
            "properties": {},
            "examples": [{}],
        },
        _implementation=_get_ticket_stats,
    ),
    Tool(
        name="get_workload_analytics",
        description="Get workload analytics for technicians and ticket queues",
        inputSchema={
            "type": "object",
            "properties": {},
            "examples": [{}],
        },
        _implementation=_get_workload_analytics,
    ),
    Tool(
        name="sla_metrics",
        description="Retrieve comprehensive SLA performance metrics dashboard",
        inputSchema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 30, "description": "Time range in days"}
            },
            "examples": [
                {"days": 30},
                {"days": 7}
            ],
        },
        _implementation=_sla_metrics,

    ),
]

# No additional reference tools
ENHANCED_TOOLS = ENHANCED_TOOLS



# ---------------------------------------------------------------------------
# Server Creation and Running
# ---------------------------------------------------------------------------

def create_server() -> Server:
    """Instantiate a Server and register tools."""
    server = Server("helpdesk-ai-agent")

    @server.list_tools()
    async def _list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.inputSchema,
            )
            for t in ENHANCED_TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> list:
        tool = next((t for t in ENHANCED_TOOLS if t.name == name), None)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
            
        args = arguments or {}
        result = await tool._implementation(**args)
        
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


def run_server() -> None:
    """Run the MCP server with stdio transport."""
    async def _main() -> None:
        # Set up logging
        config = get_config()
        logging.basicConfig(
            level=config.logging.level,
            format=config.logging.format
        )
        
        server = create_server()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    anyio.run(_main)


__all__ = [
    "MCPServerConfig",
    "get_config",
    "set_config",
    "ENHANCED_TOOLS",
    "create_server",
    "run_server"
]