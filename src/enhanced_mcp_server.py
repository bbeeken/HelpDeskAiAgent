"""Configuration management for the MCP server and stub MCP server helpers."""

from __future__ import annotations

import json
import os
import logging
import re
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import anyio
import html
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from sqlalchemy import select, func, or_
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .mcp_server import Tool, create_enhanced_server
from src.infrastructure import database as db
from src.core.services.ticket_management import (
    TicketManager,
    apply_semantic_filters,
    _PRIORITY_MAP,
)
from src.core.services.user_services import UserManager
from src.core.services.reference_data import ReferenceDataManager
from src.shared.schemas.ticket import TicketExpandedOut, TicketCreate, TicketUpdate
from pydantic import ValidationError
from src.core.repositories.models import (
    PriorityLevel,
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
from src.core.services.ticket_management import _OPEN_STATE_IDS
from src.core.services.enhanced_context import EnhancedContextManager
from src.core.services.advanced_query import AdvancedQueryManager
from src.shared.schemas.agent_data import AdvancedQuery

logger = logging.getLogger(__name__)

# ISO 8601 datetime with optional fractional seconds and timezone
_ISO_DT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)

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


def _calculate_similarity_scores(texts: list[str], query: str) -> list[float]:
    """Return cosine similarity scores between the query and each text."""
    if not query or not texts:
        return [0.0] * len(texts)

    docs = [query] + texts
    vectorizer = TfidfVectorizer().fit(docs)
    query_vec = vectorizer.transform([query])
    text_vecs = vectorizer.transform(texts)
    similarities = cosine_similarity(text_vecs, query_vec).flatten()
    return similarities.tolist()


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





def _ensure_utc(dt: datetime | None) -> datetime:
    """Return a timezone-aware datetime in UTC."""
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_ticket_overdue(ticket) -> bool:
    """Determine if a ticket is overdue based on creation date and status."""
    created = ticket.Created_Date
    if not created:
        return False
    age_hours = (datetime.now(timezone.utc) - _ensure_utc(created)).total_seconds() / 3600
    return age_hours > 24 and ticket.Closed_Date is None


def _estimate_complexity(ticket) -> str:
    """Rough complexity estimate based on subject and body length."""
    subject_length = len(getattr(ticket, "Subject", "") or "")
    body_length = len(getattr(ticket, "Ticket_Body", "") or "")
    if body_length > 500 or subject_length > 100:
        return "high"
    if body_length > 200 or subject_length > 50:
        return "medium"
    return "low"



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
            applied_filters = apply_semantic_filters(filters or {})
            
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
            applied_filters = apply_semantic_filters(filters or {})
            
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




async def _search_tickets_enhanced(
    text: str | None = None,
    query: str | None = None,  # Backward compatibility alias
    user: str | None = None,
    user_identifier: str | None = None,  # Backward compatibility alias
    days: int | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    site_id: int | None = None,
    assigned_to: str | None = None,
    unassigned_only: bool = False,
    filters: Dict[str, Any] | None = None,
    limit: int = 10,
    skip: int = 0,
    sort: list[str] | None = None,
    include_relevance_score: bool = True,
    include_highlights: bool = True,
) -> Dict[str, Any]:
    """Enhanced unified ticket search with AI-friendly features and semantic filtering."""
    try:
        # Handle backward compatibility aliases
        if text is None and query is not None:
            text = query
        if user is None and user_identifier is not None:
            user = user_identifier
        if days is None and created_after is None and created_before is None:
            days = 30

        if created_after and not _ISO_DT_PATTERN.match(created_after):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid created_after: {created_after}",
            )
        if created_before and not _ISO_DT_PATTERN.match(created_before):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid created_before: {created_before}",
            )

        async with db.SessionLocal() as db_session:
            records, total_count = await TicketManager().search_tickets(
                db_session,
                text,
                limit=limit,
                params=None,
                user=user,
                days=days,
                created_after=created_after,
                created_before=created_before,
                status=status,
                priority=priority,
                site_id=site_id,
                assigned_to=assigned_to,
                unassigned_only=unassigned_only,
                filters=filters,
                skip=skip,
                sort=sort,
            )

            applied_filters: Dict[str, Any] = {}
            if status is not None:
                applied_filters.update(apply_semantic_filters({"status": status}))
            if priority is not None:
                applied_filters.update(apply_semantic_filters({"priority": priority}))
            if site_id is not None:
                applied_filters["Site_ID"] = site_id
            if assigned_to:
                applied_filters["Assigned_Email"] = assigned_to
            if filters:
                applied_filters.update(apply_semantic_filters(filters))

            summary_filter_keys: set[str] = set()
            if status is not None:
                summary_filter_keys.add("status")
            if priority is not None:
                summary_filter_keys.add("priority")
            if site_id is not None:
                summary_filter_keys.add("site_id")
            if assigned_to:
                summary_filter_keys.add("assigned_to")
            if filters:
                summary_filter_keys.update(filters.keys())

            # Process results with AI-friendly enhancements
            data: list[dict] = []
            text_corpus: list[str] = []
            for r in records:
                item = _format_ticket_by_level(r)

                # Add AI-friendly metadata
                item["metadata"] = {
                    "age_days": (datetime.now(timezone.utc) - _ensure_utc(r.Created_Date)).days if r.Created_Date else 0,
                    "is_overdue": _is_ticket_overdue(r),
                    "complexity_estimate": _estimate_complexity(r),
                }

                if text:
                    text_corpus.append(
                        " ".join(
                            [
                                item.get("Subject", ""),
                                item.get("body_preview", ""),
                                item.get("Category_Name", ""),
                            ]
                        )
                    )

                data.append(item)

            # Calculate relevance scores using TF-IDF
            if text and include_relevance_score:
                scores = _calculate_similarity_scores(text_corpus, text)
                for itm, score in zip(data, scores):
                    itm["relevance_score"] = round(float(score), 2)

            # Add search highlighting for better AI context
            if text and include_highlights:
                for itm in data:
                    itm["highlights"] = _generate_search_highlights(itm, text)

            # Sort by relevance if text search was performed
            if text and include_relevance_score:
                data.sort(key=lambda d: d.get("relevance_score", 0), reverse=True)

            # Generate search summary for AI context
            search_summary = {
                "query_type": [],
                "filters_applied": sorted(summary_filter_keys),
                "search_scope": "all_tickets"
            }
            
            if text:
                search_summary["query_type"].append("text_search")
            if user:
                search_summary["query_type"].append("user_filter")
            if status or priority or site_id or assigned_to:
                search_summary["query_type"].append("semantic_filter")
            if unassigned_only:
                search_summary["query_type"].append("unassigned_only")

            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "total_count": total_count,
                "skip": skip,
                "limit": limit,
                "search_summary": search_summary,
                "execution_metadata": {
                    "text_query": text,
                    "user_filter": user,
                    "time_range_days": days,
                    "semantic_filters_applied": bool(status or priority),
                    "relevance_scoring": include_relevance_score and bool(text),
                    "query_complexity": "simple" if len(search_summary["query_type"]) <= 1 else "complex"
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in enhanced search_tickets: {e}")
        return {
            "status": "error",
            "error": {
                "message": str(e),
                "code": "SEARCH_EXECUTION_ERROR",
            },
        }



async def _create_ticket(**payload: Any) -> Dict[str, Any]:
    """Create a new ticket and return the created record."""
    try:
        try:
            validated = TicketCreate.model_validate(payload)
        except ValidationError as e:
            logger.error("Validation failed for create_ticket: %s", e)
            logger.debug("Invalid create_ticket payload: %s", payload)
            invalid_fields = {
                ".".join(str(loc) for loc in err.get("loc", [])): err.get("msg", "invalid")
                for err in e.errors()
            }
            return {
                "status": "error",
                "error": {
                    "message": "Validation failed",
                    "invalid_fields": invalid_fields,
                },
            }

        data_in = validated.model_dump()
        async with db.SessionLocal() as db_session:
            data_in["LastModfiedBy"] = data_in.get("LastModfiedBy") or "Gil AI"

            result = await TicketManager().create_ticket(db_session, data_in)
            if not result.success:
                await db_session.rollback()
                raise RuntimeError(result.error or "Failed to create ticket")

            await db_session.commit()

            try:
                ticket = await TicketManager().get_ticket(db_session, result.data.Ticket_ID)
                data = _format_ticket_by_level(ticket)
            except Exception as e:
                logger.error("Error formatting created ticket: %s", e)
                data = {**data_in, "Ticket_ID": result.data.Ticket_ID}

            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in create_ticket: {e}")
        logger.debug("create_ticket payload: %s", payload)
        return {"status": "error", "error": str(e)}


async def _update_ticket(ticket_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing ticket.

    There are two valid ways to specify update fields:

    1. **Semantic names** such as ``status``, ``priority`` or
       ``assignee_email``. These human‑friendly keys are translated into the
       corresponding database columns using the ticket field mapping table in
       :func:`ticket_management.apply_semantic_filters`.
    2. **Raw database columns/IDs** like ``Ticket_Status_ID`` or
       ``Severity_ID`` when the exact numeric values are known.

    The mapping table defines which semantic fields map to which raw columns
    and acceptable values for each.
    """
    try:
        async with db.SessionLocal() as db_session:
            try:
                applied_updates = apply_semantic_filters(updates)
            except ValueError as e:
                return {"status": "error", "error": e.args[0]}

            field_aliases = {
                "Ticket_Status_ID": ["status", "ticket_status", "Ticket_Status_ID"],
                "Severity_ID": ["priority", "priority_level", "Severity_ID"],
            }

            for field, value in list(applied_updates.items()):
                if isinstance(value, list):
                    if len(value) == 1:
                        applied_updates[field] = value[0]
                    else:
                        aliases = field_aliases.get(field, [field])
                        provided = next((updates[a] for a in aliases if a in updates), value)
                        opts = ", ".join(str(v) for v in value)
                        label = aliases[0]
                        return {
                            "status": "error",
                            "error": f"Ambiguous {label} value '{provided}'. Valid options: {opts}",
                        }

            message = applied_updates.pop("message", None)

            if not applied_updates:
                return {"status": "error", "error": "No updates provided"}

            try:
                validated = TicketUpdate.model_validate(applied_updates)
            except ValidationError as e:
                logger.error("Validation failed for update_ticket: %s", e)
                logger.debug("Invalid update_ticket payload: %s", updates)
                invalid_fields = {
                    ".".join(str(loc) for loc in err.get("loc", [])): err.get("msg", "invalid")
                    for err in e.errors()
                }
                return {
                    "status": "error",
                    "error": {
                        "message": "Validation failed",
                        "invalid_fields": invalid_fields,
                    },
                }

            applied_updates = validated.model_dump(exclude_unset=True)

            if applied_updates.get("Ticket_Status_ID") == 3 and "Closed_Date" not in applied_updates:
                applied_updates["Closed_Date"] = datetime.now(timezone.utc)

            if "Assigned_Email" in applied_updates and "Assigned_Name" not in applied_updates:
                user_info = await UserManager().get_user_by_email(applied_updates["Assigned_Email"])
                display_name = user_info.get("displayName")
                if display_name and display_name != applied_updates["Assigned_Email"]:
                    applied_updates["Assigned_Name"] = display_name

            try:
                updated = await TicketManager().update_ticket(
                    db_session,
                    ticket_id,
                    applied_updates,
                    modified_by="Gil AI",
                )
                if not updated:
                    return {"status": "error", "error": f"Ticket {ticket_id} not found"}

                if message:
                    await TicketManager().post_message(
                        db_session,
                        ticket_id,
                        message,
                        applied_updates.get("Assigned_Email", "system"),
                        sender_name=applied_updates.get("Assigned_Name"),
                    )

                await db_session.commit()

            except Exception as e:
                await db_session.rollback()
                logger.error(f"Error updating ticket {ticket_id}: {e}")
                return {"status": "error", "error": str(e)}

            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = _format_ticket_by_level(ticket)

            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in update_ticket: {e}")
        logger.debug("update_ticket payload: %s", updates)
        return {"status": "error", "error": str(e)}


async def _bulk_update_tickets(
    ticket_ids: list[int],
    updates: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Apply the same updates to multiple tickets.

    The ``updates`` payload follows the same rules as :func:`_update_ticket` and
    may use either semantic field names (translated via the mapping table) or
    raw database columns/IDs.
    """
    try:
        if not ticket_ids:
            return {"status": "error", "error": "No ticket IDs provided"}
        if not updates:
            return {"status": "error", "error": "No updates provided"}
        async with db.SessionLocal() as db_session:
            mgr = TicketManager()
            try:
                applied_updates = apply_semantic_filters(updates)
            except ValueError as e:
                return {"status": "error", "error": e.args[0]}

            field_aliases = {
                "Ticket_Status_ID": ["status", "ticket_status", "Ticket_Status_ID"],
                "Severity_ID": ["priority", "priority_level", "Severity_ID"],
            }

            for field, value in list(applied_updates.items()):
                if isinstance(value, list):
                    if len(value) == 1:
                        applied_updates[field] = value[0]
                    else:
                        aliases = field_aliases.get(field, [field])
                        provided = next((updates[a] for a in aliases if a in updates), value)
                        opts = ", ".join(str(v) for v in value)
                        label = aliases[0]
                        return {
                            "status": "error",
                            "error": f"Ambiguous {label} value '{provided}'. Valid options: {opts}",
                        }

            updated: list[Dict[str, Any]] = []
            failed: list[Dict[str, Any]] = []

            try:
                for tid in ticket_ids:
                    try:
                        result = await mgr.update_ticket(
                            db_session,
                            tid,
                            applied_updates,
                            modified_by="Gil AI",
                        )
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
                await db_session.rollback()
                logger.error(f"Error in bulk_update_tickets: {e}")
                return {"status": "error", "error": str(e)}
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
                sender_name=sender_name,
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
                    "FileContent": base64.b64encode(a.FileContent).decode("utf-8") if a.FileContent else None,
                    "Binary": base64.b64encode(a.Binary).decode("utf-8") if a.Binary else None,
                    "ContentBytes": base64.b64encode(a.ContentBytes).decode("utf-8") if a.ContentBytes else None,
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
                applied_filters = apply_semantic_filters(filters)
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


        valid_types = {
            "overview",
            "ticket_counts",
            "workload",
            "sla_performance",
            "trends",
            "overdue_tickets",
            "status_counts",
        }

        if type in {"status_counts"}:
            return JSONResponse(status_code=404, content={"detail": "Unsupported analytics type"})

        return {
            "status": "error",
            "error": f"Unknown analytics type: {type}. Valid types: {', '.join(sorted(valid_types))}",
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
                .filter(TicketStatus.ID.in_(_OPEN_STATE_IDS))
            )
            
            # Apply filters
            if filters:
                applied_filters = apply_semantic_filters(filters)
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
                result = await db_session.execute(select(PriorityLevel).order_by(PriorityLevel.ID))
                records = result.scalars().all()
                total_count = len(records)
                if skip:
                    records = records[skip:]
                if limit:
                    records = records[:limit]
                field = "Priority_Level"
                ids = [r.Label for r in records]
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
                        "level": r.Label,
                        "semantic_name": _PRIORITY_MAP.get(r.Label.lower(), r.Label) if r.Label else None,
                    }
                    key = r.Label
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
        .filter(TicketStatus.ID.in_(_OPEN_STATE_IDS))
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
            context = await mgr.get_ticket_full_context(
                ticket_id,
                include_user_history=False,
                include_related_tickets=False,
            )
            
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

            # Retrieve ticket counts grouped by various dimensions
            status_counts = await mgr._get_ticket_counts_by_status()
            priority_counts = await mgr._get_ticket_counts_by_priority()
            site_counts = await mgr._get_ticket_counts_by_site()
            category_counts = await mgr._get_ticket_counts_by_category()

            # Calculate totals from status counts
            total_tickets = sum(status_counts.values())
            open_tickets = sum(
                count
                for label, count in status_counts.items()
                if "open" in label.lower() or "progress" in label.lower()
            )

            data = {
                "by_status": status_counts,
                "by_priority": priority_counts,
                "by_site": site_counts,
                "by_category": category_counts,
                "summary": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_tickets": total_tickets,
                    "open_tickets": open_tickets,
                    "closed_tickets": total_tickets - open_tickets,
                },
            }

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
        description=(
            "Update an existing ticket using either semantic field names or raw"
            " IDs; see the field mapping table for supported values"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID to update"},
                "updates": {
                    "type": "object",
                    "description": (
                        "Fields to change. Accepts semantic keys like 'status' or"
                        " raw columns such as 'Ticket_Status_ID' (see mapping table)"
                    ),
                },
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
        description=(
            "Update multiple tickets at once using semantic fields or raw IDs"
            " as defined in the field mapping table"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of ticket IDs"},
                "updates": {
                    "type": "object",
                    "description": (
                        "Fields to apply to each ticket; accepts semantic names or"
                        " raw columns (see mapping table)"
                    ),
                },
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
    description="Universal ticket search tool supporting text queries, user filtering, date ranges, and advanced filters. Automatically handles semantic filtering (e.g. 'open' status includes multiple states). Designed for AI agents to find tickets efficiently.",
    inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Free-text query for ticket subject and body"},
                    "query": {"type": "string", "description": "Alias for 'text' (backward compatibility)"},
                    "user": {"type": "string", "description": "Filter by user email or name"},
                    "user_identifier": {"type": "string", "description": "Alias for 'user' (backward compatibility)"},
                    "days": {"type": "integer", "default": 30, "minimum": 0,
                        "description": "Limit to tickets created in the last N days (0 = all time). Ignored when created_after or created_before are provided"},
                    "created_after": {"type": "string", "format": "date-time",
                        "description": "Return tickets created on or after this ISO 8601 datetime"},
                    "created_before": {"type": "string", "format": "date-time",
                        "description": "Return tickets created on or before this ISO 8601 datetime"},
                    "status": {"type": "string", "enum": ["open", "in_progress", "resolved", "closed"],
                        "description": "Ticket status filter"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"],
                        "description": "Priority level filter"},
                    "site_id": {"type": "integer", "description": "Filter by specific site ID"},
                    "assigned_to": {"type": "string", "description": "Filter by assignee email"},
                    "unassigned_only": {"type": "boolean", "default": False,
                        "description": "If true, only return unassigned tickets"},
                    "filters": {"type": "object", "description": "Additional key/value filters for advanced use"},
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100,
                        "description": "Maximum number of results to return"},
                    "skip": {"type": "integer", "default": 0, "minimum": 0,
                        "description": "Number of results to skip (for pagination)"},
                    "sort": {"type": "array", "items": {"type": "string"},
                        "description": "Sort fields (prefix with '-' for descending)", "default": ["-Created_Date"]},
                    "include_relevance_score": {"type": "boolean", "default": True,
                        "description": "Include relevance scores for text searches"},
                    "include_highlights": {"type": "boolean", "default": True,
                        "description": "Include search term highlighting in results"}
                },
                "examples": [
                    {"text": "printer error", "status": "open", "days": 7, "limit": 5},
                    {"user": "tech@example.com", "status": "open", "sort": ["-Created_Date"]},
                    {"text": "network issues", "user": "alice@example.com", "priority": "high", "days": 30},
                    {"status": "open", "unassigned_only": True, "sort": ["-Priority_Level"], "limit": 20},
                    {"site_id": 1, "status": "open", "assigned_to": "tech@heinzcorps.com"},
                    {"text": "email", "created_after": "2024-01-01T00:00:00Z", "created_before": "2024-12-31T23:59:59Z"}
                ]
    },
    _implementation=_search_tickets_enhanced,
  ),
    Tool(
        name="get_analytics",
        description="Retrieve analytics reports",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Analytics report type"},
                "type": {
                    "type": "string",
                    "enum": [
                        "overview",
                        "ticket_counts",
                        "workload",
                        "sla_performance",
                        "trends",
                        "overdue_tickets",
                        "status_counts",
                    ],

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


def create_app():
    from fastapi import FastAPI
    app = FastAPI()
    server = create_enhanced_server()
    app.state.mcp_server = server
    app.state.mcp_ready = True

    @app.on_event("startup")
    async def startup_mcp():
        app.state.mcp_server = create_enhanced_server()
        app.state.mcp_ready = True

    return app


__all__ = [
    "MCPServerConfig",
    "get_config",
    "set_config",
    "ENHANCED_TOOLS",
    "create_server",
    "run_server",
    "create_app",
]
