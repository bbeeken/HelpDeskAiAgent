"""Configuration management for the MCP server and stub MCP server helpers."""

from __future__ import annotations

import json
import os
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
from src.core.repositories.models import Priority, Ticket, TicketStatus, VTicketMasterExpanded
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
                translated["Ticket_Status_ID"] = _STATUS_MAP.get(value.lower(), value)
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

async def _get_ticket(ticket_id: int) -> Dict[str, Any]:
    """Retrieve a ticket by ID and return full details."""
    try:
        async with db.SessionLocal() as db_session:
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            if not ticket:
                return {"status": "error", "error": f"Ticket {ticket_id} not found"}
            data = _format_ticket_by_level(ticket)
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
            applied_updates["LastModified"] = datetime.now(timezone.utc)
            
            updated = await TicketManager().update_ticket(db_session, ticket_id, applied_updates)
            if not updated:
                await db_session.rollback()
                return {"status": "error", "error": f"Ticket {ticket_id} not found"}
                
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
        async with db.SessionLocal() as db_session:
            mgr = TicketManager()
            applied_updates = _apply_semantic_filters(updates)
            applied_updates["LastModified"] = datetime.now(timezone.utc)
            
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


async def _close_ticket(
    ticket_id: int,
    resolution: str,
    status_id: int = 4,
) -> Dict[str, Any]:
    """Close a ticket with a resolution."""
    try:
        async with db.SessionLocal() as db_session:
            updates = {
                "Ticket_Status_ID": status_id,
                "Resolution": resolution,
                "Closed_Date": datetime.now(timezone.utc),
                "LastModified": datetime.now(timezone.utc)
            }
            
            updated = await TicketManager().update_ticket(db_session, ticket_id, updates)
            if not updated:
                await db_session.rollback()
                return {"status": "error", "error": f"Ticket {ticket_id} not found"}
                
            await db_session.commit()
            
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = _format_ticket_by_level(ticket)
            
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in close_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _assign_ticket(
    ticket_id: int,
    assignee_email: str,
    assignee_name: str | None = None,
) -> Dict[str, Any]:
    """Assign a ticket to a technician."""
    try:
        async with db.SessionLocal() as db_session:
            updates = {
                "Assigned_Email": assignee_email,
                "Assigned_Name": assignee_name or assignee_email,
                "LastModified": datetime.now(timezone.utc)
            }
            
            updated = await TicketManager().update_ticket(db_session, ticket_id, updates)
            if not updated:
                await db_session.rollback()
                return {"status": "error", "error": f"Ticket {ticket_id} not found"}
                
            await db_session.commit()
            
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = _format_ticket_by_level(ticket)
            
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in assign_ticket: {e}")
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


async def _escalate_ticket(
    ticket_id: int,
    severity_id: int,
    assignee_email: str,
    assignee_name: str | None = None,
    message: str | None = None,
) -> Dict[str, Any]:
    """Escalate a ticket by updating severity and assignee."""
    try:
        async with db.SessionLocal() as db_session:
            updates = {
                "Severity_ID": severity_id,
                "Assigned_Email": assignee_email,
                "Assigned_Name": assignee_name or assignee_email,
                "LastModified": datetime.now(timezone.utc)
            }
            
            updated = await TicketManager().update_ticket(db_session, ticket_id, updates)
            if not updated:
                await db_session.rollback()
                return {"status": "error", "error": f"Ticket {ticket_id} not found"}
            
            await db_session.commit()
            
            # Add escalation note
            if message:
                note = message
            else:
                note = f"Ticket escalated to severity {severity_id} and assigned to {assignee_name or assignee_email}"
                
            await TicketManager().post_message(
                db_session,
                ticket_id,
                note,
                assignee_email,
                assignee_name or assignee_email,
            )
            await db_session.commit()

            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = _format_ticket_by_level(ticket)
            
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in escalate_ticket: {e}")
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


async def _get_analytics(type: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return analytics data based on requested type."""
    try:
        async with db.SessionLocal() as db_session:
            data = None
            
            if type == "status_counts":
                result = await tickets_by_status(db_session)
                data = result.data if hasattr(result, "data") and hasattr(result, "success") and result.success else []
                
            elif type == "site_counts":
                data = await open_tickets_by_site(db_session)
                
            elif type == "technician_workload":
                data = await open_tickets_by_user(db_session, params)
                
            elif type == "sla_breaches":
                days = params.get("sla_days", 2) if params else 2
                status_ids = params.get("status_ids") if params else None
                breach_count = await sla_breaches(
                    db_session, sla_days=days, status_ids=status_ids, filters=params
                )
                data = {
                    "breaches": breach_count,
                    "sla_days": days,
                    "filters_applied": bool(params)
                }
                
            elif type == "trends":
                days = params.get("days", 7) if params else 7
                data = await ticket_trend(db_session, days)
                
            else:
                return {"status": "error", "error": f"Unknown analytics type: {type}"}
                
            return {
                "status": "success",
                "data": data,
                "type": type,
                "params": params
            }
    except Exception as e:
        logger.error(f"Error in get_analytics: {e}")
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


async def _list_reference_data(
    type: str,
    limit: int = 10,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """Return reference data such as sites, assets, vendors, or categories."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = ReferenceDataManager()
            
            if type == "sites":
                records = await mgr.list_sites(
                    db_session, limit=limit, filters=filters, sort=sort
                )
            elif type == "assets":
                records = await mgr.list_assets(
                    db_session, limit=limit, filters=filters, sort=sort
                )
            elif type == "vendors":
                records = await mgr.list_vendors(
                    db_session, limit=limit, filters=filters, sort=sort
                )
            elif type == "categories":
                records = await mgr.list_categories(
                    db_session, filters=filters, sort=sort
                )
            else:
                return {"status": "error", "error": f"Unknown reference data type: {type}"}
                
            # Convert to dictionaries and clean up
            data = []
            for r in records:
                item = r.__dict__.copy()
                # Remove SQLAlchemy internal attributes
                item.pop('_sa_instance_state', None)
                data.append(item)
                
            return {
                "status": "success",
                "data": data,
                "type": type,
                "count": len(data)
            }
    except Exception as e:
        logger.error(f"Error in list_reference_data: {e}")
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


async def _list_sites_enhanced(
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """List sites with ticket counts."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = ReferenceDataManager()
            sites = await mgr.list_sites(
                db_session,
                skip=skip,
                limit=limit,
                filters=filters,
                sort=sort,
            )
            
            # Get ticket counts
            ids = [s.ID for s in sites]
            open_counts = await _count_open_tickets_by_field(db_session, "Site_ID", ids)
            total_counts = await _count_total_tickets_by_field(db_session, "Site_ID", ids)
            
            # Build enhanced data
            data = []
            for s in sites:
                item = s.__dict__.copy()
                item.pop('_sa_instance_state', None)
                item["open_tickets"] = open_counts.get(s.ID, 0)
                item["total_tickets"] = total_counts.get(s.ID, 0)
                item["closed_tickets"] = item["total_tickets"] - item["open_tickets"]
                data.append(item)
                
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "skip": skip,
                "limit": limit
            }
    except Exception as e:
        logger.error(f"Error in list_sites_enhanced: {e}")
        return {"status": "error", "error": str(e)}


async def _list_assets_enhanced(
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """List assets with ticket counts."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = ReferenceDataManager()
            assets = await mgr.list_assets(
                db_session,
                skip=skip,
                limit=limit,
                filters=filters,
                sort=sort,
            )
            
            # Get ticket counts
            ids = [a.ID for a in assets]
            open_counts = await _count_open_tickets_by_field(db_session, "Asset_ID", ids)
            total_counts = await _count_total_tickets_by_field(db_session, "Asset_ID", ids)
            
            # Build enhanced data
            data = []
            for a in assets:
                item = a.__dict__.copy()
                item.pop('_sa_instance_state', None)
                item["open_tickets"] = open_counts.get(a.ID, 0)
                item["total_tickets"] = total_counts.get(a.ID, 0)
                item["closed_tickets"] = item["total_tickets"] - item["open_tickets"]
                data.append(item)
                
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "skip": skip,
                "limit": limit
            }
    except Exception as e:
        logger.error(f"Error in list_assets_enhanced: {e}")
        return {"status": "error", "error": str(e)}


async def _list_vendors_enhanced(
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """List vendors with ticket counts."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = ReferenceDataManager()
            vendors = await mgr.list_vendors(
                db_session,
                skip=skip,
                limit=limit,
                filters=filters,
                sort=sort,
            )
            
            # Get ticket counts
            ids = [v.ID for v in vendors]
            open_counts = await _count_open_tickets_by_field(db_session, "Assigned_Vendor_ID", ids)
            total_counts = await _count_total_tickets_by_field(db_session, "Assigned_Vendor_ID", ids)
            
            # Build enhanced data
            data = []
            for v in vendors:
                item = v.__dict__.copy()
                item.pop('_sa_instance_state', None)
                item["open_tickets"] = open_counts.get(v.ID, 0)
                item["total_tickets"] = total_counts.get(v.ID, 0)
                item["closed_tickets"] = item["total_tickets"] - item["open_tickets"]
                data.append(item)
                
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "skip": skip,
                "limit": limit
            }
    except Exception as e:
        logger.error(f"Error in list_vendors_enhanced: {e}")
        return {"status": "error", "error": str(e)}


async def _list_categories_enhanced(
    limit: int = 10,
    skip: int = 0,
    filters: Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Dict[str, Any]:
    """List categories with ticket counts."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = ReferenceDataManager()
            cats = await mgr.list_categories(
                db_session,
                filters=filters,
                sort=sort,
            )
            
            # Apply pagination to categories
            total_count = len(cats)
            if skip:
                cats = cats[skip:]
            if limit:
                cats = cats[:limit]
            
            # Get ticket counts
            ids = [c.ID for c in cats]
            open_counts = await _count_open_tickets_by_field(
                db_session,
                "Ticket_Category_ID",
                ids,
            )
            total_counts = await _count_total_tickets_by_field(
                db_session,
                "Ticket_Category_ID",
                ids,
            )
            
            # Build enhanced data
            data = []
            for c in cats:
                item = c.__dict__.copy()
                item.pop('_sa_instance_state', None)
                item["open_tickets"] = open_counts.get(c.ID, 0)
                item["total_tickets"] = total_counts.get(c.ID, 0)
                item["closed_tickets"] = item["total_tickets"] - item["open_tickets"]
                data.append(item)
                
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "total_count": total_count,
                "skip": skip,
                "limit": limit
            }
    except Exception as e:
        logger.error(f"Error in list_categories_enhanced: {e}")
        return {"status": "error", "error": str(e)}


async def _list_priorities() -> Dict[str, Any]:
    """Return available priority levels ordered by ID."""
    try:
        async with db.SessionLocal() as db_session:
            result = await db_session.execute(select(Priority).order_by(Priority.ID))
            records = result.scalars().all()
            
            data = [
                {
                    "id": p.ID,
                    "level": p.Level,
                    "semantic_name": _PRIORITY_MAP.get(p.Level.lower(), p.Level) if p.Level else None
                }
                for p in records
            ]
            
            return {
                "status": "success",
                "data": data,
                "count": len(data)
            }
    except Exception as e:
        logger.error(f"Error in list_priorities: {e}")
        return {"status": "error", "error": str(e)}


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
        description="Get a ticket by ID with full details",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer", "description": "The ticket ID"}},
            "required": ["ticket_id"],
            "examples": [{"ticket_id": 123}],
        },
        _implementation=_get_ticket,
    ),
    Tool(
        name="list_tickets",
        description="List tickets with optional semantic filters (e.g., status='open', priority='high')",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10, "description": "Maximum number of tickets to return"},
                "skip": {"type": "integer", "default": 0, "description": "Number of tickets to skip"},
                "filters": {"type": "object", "description": "Filter criteria (supports semantic values like status='open')"},
                "sort": {"type": "array", "items": {"type": "string"}, "description": "Sort fields (prefix with - for descending)"},
            },
            "examples": [
                {"limit": 5, "filters": {"status": "open"}},
                {"limit": 10, "filters": {"priority": "high"}, "sort": ["-Created_Date"]}
            ],
        },
        _implementation=_list_tickets,
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
        name="close_ticket",
        description="Close a ticket with resolution",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID to close"},
                "resolution": {"type": "string", "description": "Resolution description"},
                "status_id": {"type": "integer", "default": 4, "description": "Closed status ID"},
            },
            "required": ["ticket_id", "resolution"],
            "examples": [
                {"ticket_id": 1, "resolution": "Issue resolved by restarting service"}
            ],
        },
        _implementation=_close_ticket,
    ),
    Tool(
        name="assign_ticket",
        description="Assign a ticket to a technician",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID"},
                "assignee_email": {"type": "string", "description": "Assignee's email address"},
                "assignee_name": {"type": "string", "description": "Assignee's display name"},
            },
            "required": ["ticket_id", "assignee_email"],
            "examples": [
                {"ticket_id": 1, "assignee_email": "tech@example.com", "assignee_name": "John Doe"}
            ],
        },
        _implementation=_assign_ticket,
    ),
    Tool(
        name="escalate_ticket",
        description="Escalate a ticket by updating severity and assignment",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID"},
                "severity_id": {"type": "integer", "description": "New severity level (1=Critical, 2=High, 3=Medium, 4=Low)"},
                "assignee_email": {"type": "string", "description": "Email of escalation assignee"},
                "assignee_name": {"type": "string", "description": "Name of escalation assignee"},
                "message": {"type": "string", "description": "Escalation note"},
            },
            "required": ["ticket_id", "severity_id", "assignee_email"],
            "examples": [
                {
                    "ticket_id": 123,
                    "severity_id": 1,
                    "assignee_email": "senior@example.com",
                    "message": "Escalating due to production impact"
                }
            ],
        },
        _implementation=_escalate_ticket,
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
        description="Search tickets by text with relevance scoring",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "limit": {"type": "integer", "default": 10, "description": "Maximum results"},
            },
            "required": ["query"],
            "examples": [
                {"query": "printer", "limit": 5},
                {"query": "network connectivity"}
            ],
        },
        _implementation=_search_tickets,
    ),
    Tool(
        name="search_tickets_advanced",
        description="Advanced ticket search with multiple criteria",
        inputSchema=AdvancedQuery.model_json_schema(),
        _implementation=_search_tickets_advanced,
    ),
    Tool(
        name="get_tickets_by_user",
        description="Retrieve tickets associated with a user",
        inputSchema={
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "User email or identifier"},
                "skip": {"type": "integer", "default": 0},
                "limit": {"type": "integer", "default": 100},
                "status": {"type": "string", "description": "Filter by status"},
                "filters": {"type": "object", "description": "Additional filters"},
            },
            "required": ["identifier"],
            "examples": [
                {"identifier": "user@example.com", "status": "open"},
                {"identifier": "john.doe@company.com", "limit": 20}
            ],
        },
        _implementation=_get_tickets_by_user,
    ),
    Tool(
        name="get_open_tickets",
        description="List open tickets with timeframe and filtering",
        inputSchema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 3650, "description": "Tickets from last N days"},
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "examples": [
                {"days": 30, "limit": 20},
                {"days": 7, "filters": {"priority": "high"}, "sort": ["-Created_Date"]}
            ],
        },
        _implementation=_get_open_tickets,
    ),
    Tool(
        name="get_analytics",
        description="Retrieve various analytics data",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["status_counts", "site_counts", "technician_workload", "sla_breaches", "trends"],
                    "description": "Type of analytics to retrieve"
                },
                "params": {"type": "object", "description": "Additional parameters for the analytics"},
            },
            "required": ["type"],
            "examples": [
                {"type": "status_counts"},
                {"type": "trends", "params": {"days": 7}},
                {"type": "sla_breaches", "params": {"sla_days": 2}}
            ],
        },
        _implementation=_get_analytics,
    ),
    Tool(
        name="get_sla_metrics",
        description="Get SLA compliance statistics",
        inputSchema={
            "type": "object",
            "properties": {
                "sla_days": {"type": "integer", "default": 2, "description": "SLA threshold in days"},
                "filters": {"type": "object", "description": "Additional filters"},
                "status_ids": {"type": "array", "items": {"type": "integer"}, "description": "Filter by status IDs"},
            },
            "examples": [
                {"sla_days": 2},
                {"sla_days": 3, "filters": {"Site_ID": 1}}
            ],
        },
        _implementation=_get_sla_metrics,
    ),
    Tool(
        name="list_reference_data",
        description="List reference data (sites, assets, vendors, categories)",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["sites", "assets", "vendors", "categories"],
                    "description": "Type of reference data"
                },
                "limit": {"type": "integer", "default": 10},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["type"],
            "examples": [
                {"type": "sites", "limit": 10},
                {"type": "categories", "sort": ["Label"]}
            ],
        },
        _implementation=_list_reference_data,
    ),
    Tool(
        name="list_priorities",
        description="List available priority levels",
        inputSchema={
            "type": "object",
            "properties": {},
            "examples": [{}],
        },
        _implementation=_list_priorities,
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
        name="advanced_search",
        description="Run a detailed ticket search with advanced options",
        inputSchema={
            "type": "object",
            "properties": {
                "text_search": {"type": "string", "description": "Text to search for"},
                "limit": {"type": "integer", "default": 100},
                "offset": {"type": "integer", "default": 0},
            },
            "examples": [
                {"text_search": "printer issue", "limit": 10},
                {"text_search": "network", "limit": 50, "offset": 20}
            ],
        },
        _implementation=_advanced_search,
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

# Enhanced reference data tools with ticket counts
ENHANCED_REFERENCE_TOOLS: List[Tool] = [
    Tool(
        name="list_sites_enhanced",
        description="List sites with open/total ticket counts",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "examples": [
                {"limit": 20},
                {"limit": 10, "sort": ["Label"]}
            ],
        },
        _implementation=_list_sites_enhanced,
    ),
    Tool(
        name="list_assets_enhanced",
        description="List assets with open/total ticket counts",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "examples": [
                {"limit": 20},
                {"limit": 10, "filters": {"Site_ID": 1}}
            ],
        },
        _implementation=_list_assets_enhanced,
    ),
    Tool(
        name="list_vendors_enhanced",
        description="List vendors with open/total ticket counts",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "examples": [
                {"limit": 20},
                {"limit": 10, "sort": ["Label"]}
            ],
        },
        _implementation=_list_vendors_enhanced,
    ),
    Tool(
        name="list_categories_enhanced",
        description="List categories with open/total ticket counts",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "examples": [
                {"limit": 20},
                {"limit": 10, "sort": ["Name"]}
            ],
        },
        _implementation=_list_categories_enhanced,
    ),
]

# Combine all tools
# Rebuild ENHANCED_TOOLS with all tool definitions while preserving order and
# eliminating any duplicate tool names. This ensures ``list_tools`` exposes a
# clean set regardless of how tools were defined above.
_combined_tools: List[Tool] = []
_seen_names = set()
for _tool in ENHANCED_TOOLS + ENHANCED_REFERENCE_TOOLS:
    if _tool.name not in _seen_names:
        _combined_tools.append(_tool)
        _seen_names.add(_tool.name)

ENHANCED_TOOLS = _combined_tools


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