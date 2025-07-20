"""Advanced querying capabilities for agent data access."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.models import VTicketMasterExpanded, TicketMessage, TicketAttachment
from src.shared.schemas.agent_data import AdvancedQuery, QueryResult
from .enhanced_context import EnhancedContextManager

logger = logging.getLogger(__name__)


class AdvancedQueryManager:
    """Advanced querying tools for flexible agent data access."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.context_manager = EnhancedContextManager(db)

    async def query_tickets_advanced(self, query: AdvancedQuery) -> QueryResult:
        """Execute advanced ticket query with rich results."""

        start_time = datetime.now()

        # Build base query
        stmt = select(VTicketMasterExpanded)

        # Apply filters
        conditions = []

        # Text search
        if query.text_search:
            text_conditions = []
            for field in query.search_fields:
                if hasattr(VTicketMasterExpanded, field):
                    text_conditions.append(
                        getattr(VTicketMasterExpanded, field).ilike(f"%{query.text_search}%")
                    )
            if text_conditions:
                conditions.append(or_(*text_conditions))

        # Date filters
        if query.date_range:
            if query.date_range.get("start"):
                conditions.append(VTicketMasterExpanded.Created_Date >= query.date_range["start"])
            if query.date_range.get("end"):
                conditions.append(VTicketMasterExpanded.Created_Date <= query.date_range["end"])

        if query.created_after:
            conditions.append(VTicketMasterExpanded.Created_Date >= query.created_after)

        if query.created_before:
            conditions.append(VTicketMasterExpanded.Created_Date <= query.created_before)

        # Status and priority filters
        if query.status_filter:
            # Handle both status IDs and labels
            status_conditions = []
            for status in query.status_filter:
                if isinstance(status, int):
                    status_conditions.append(VTicketMasterExpanded.Ticket_Status_ID == status)
                else:
                    status_conditions.append(VTicketMasterExpanded.Ticket_Status_Label.ilike(f"%{status}%"))
            conditions.append(or_(*status_conditions))

        if query.priority_filter:
            conditions.append(VTicketMasterExpanded.Priority_ID.in_(query.priority_filter))

        # Assignment filters
        if query.assigned_to:
            conditions.append(VTicketMasterExpanded.Assigned_Email.in_(query.assigned_to))

        if query.unassigned_only:
            conditions.append(VTicketMasterExpanded.Assigned_Email.is_(None))

        # Location and asset filters
        if query.site_filter:
            conditions.append(VTicketMasterExpanded.Site_ID.in_(query.site_filter))

        if query.asset_filter:
            conditions.append(VTicketMasterExpanded.Asset_ID.in_(query.asset_filter))

        if query.category_filter:
            conditions.append(VTicketMasterExpanded.Ticket_Category_ID.in_(query.category_filter))

        # User filters
        if query.contact_email:
            conditions.append(VTicketMasterExpanded.Ticket_Contact_Email.in_(query.contact_email))

        if query.contact_name:
            conditions.append(VTicketMasterExpanded.Ticket_Contact_Name.ilike(f"%{query.contact_name}%"))

        # Custom filters
        for field, value in query.custom_filters.items():
            if hasattr(VTicketMasterExpanded, field):
                if isinstance(value, list):
                    conditions.append(getattr(VTicketMasterExpanded, field).in_(value))
                else:
                    conditions.append(getattr(VTicketMasterExpanded, field) == value)

        # Apply all conditions
        if conditions:
            stmt = stmt.filter(and_(*conditions))

        # Get total count for pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = await self.db.scalar(count_stmt) or 0

        # Apply sorting
        for sort_spec in query.sort_by:
            field = sort_spec.get("field", "Created_Date")
            direction = sort_spec.get("direction", "desc")

            if hasattr(VTicketMasterExpanded, field):
                attr = getattr(VTicketMasterExpanded, field)
                if direction.lower() == "desc":
                    stmt = stmt.order_by(attr.desc())
                else:
                    stmt = stmt.order_by(attr.asc())

        # Apply pagination
        stmt = stmt.offset(query.offset).limit(query.limit)

        # Execute query
        result = await self.db.execute(stmt)
        tickets = result.scalars().all()

        # Convert to dict format
        ticket_dicts = []
        for ticket in tickets:
            ticket_dict = {
                column.name: getattr(ticket, column.name)
                for column in ticket.__table__.columns
            }

            # Add related data if requested
            if query.include_messages:
                ticket_dict["messages"] = await self.context_manager._get_ticket_messages(ticket.Ticket_ID)

            if query.include_attachments:
                ticket_dict["attachments"] = await self.context_manager._get_ticket_attachments(ticket.Ticket_ID)

            if query.include_user_context:
                try:
                    ticket_dict["user_profile"] = await self.context_manager.user_manager.get_user_by_email(
                        ticket.Ticket_Contact_Email
                    )
                except:
                    ticket_dict["user_profile"] = None

            ticket_dicts.append(ticket_dict)

        # Calculate execution time
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000

        # Generate aggregations
        aggregations = await self._generate_query_aggregations(tickets)

        # Assess query complexity
        complexity = self._assess_query_complexity(query, len(conditions))

        return QueryResult(
            tickets=ticket_dicts,
            total_count=total_count,
            execution_time_ms=execution_time,
            query_complexity=complexity,
            cache_used=False,  # Could implement caching later
            aggregations=aggregations,
            result_quality={
                "data_completeness": self._assess_data_completeness(ticket_dicts),
                "result_diversity": self._assess_result_diversity(ticket_dicts)
            }
        )

    async def _generate_query_aggregations(self, tickets) -> Dict[str, Any]:
        """Generate useful aggregations from query results."""
        if not tickets:
            return {}

        # Status breakdown
        status_counts = {}
        priority_counts = {}
        site_counts = {}
        category_counts = {}

        for ticket in tickets:
            # Status
            status = ticket.Ticket_Status_Label or "Unknown"
            status_counts[status] = status_counts.get(status, 0) + 1

            # Priority
            priority = ticket.Priority_Level or "Medium"
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

            # Site
            site = ticket.Site_Label or "Unknown"
            site_counts[site] = site_counts.get(site, 0) + 1

            # Category
            category = ticket.Ticket_Category_Label or "Unknown"
            category_counts[category] = category_counts.get(category, 0) + 1

        return {
            "status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
            "site_breakdown": site_counts,
            "category_breakdown": category_counts,
            "total_results": len(tickets)
        }

    def _assess_query_complexity(self, query: AdvancedQuery, condition_count: int) -> str:
        """Assess the complexity of the query."""
        complexity_score = 0

        # Add complexity for various factors
        if query.text_search:
            complexity_score += 2

        complexity_score += condition_count

        if query.include_messages or query.include_attachments or query.include_user_context:
            complexity_score += 3

        if complexity_score <= 3:
            return "simple"
        elif complexity_score <= 7:
            return "medium"
        else:
            return "complex"

    def _assess_data_completeness(self, tickets: List[Dict[str, Any]]) -> float:
        """Assess how complete the returned data is."""
        if not tickets:
            return 0.0

        # Check for key fields
        key_fields = ["Subject", "Ticket_Body", "Created_Date", "Ticket_Status_Label"]

        total_fields = len(tickets) * len(key_fields)
        complete_fields = 0

        for ticket in tickets:
            for field in key_fields:
                if ticket.get(field) is not None:
                    complete_fields += 1

        return complete_fields / total_fields if total_fields > 0 else 0.0

    def _assess_result_diversity(self, tickets: List[Dict[str, Any]]) -> float:
        """Assess diversity of results (different statuses, priorities, etc.)."""
        if not tickets:
            return 0.0

        unique_statuses = set(t.get("Ticket_Status_Label") for t in tickets if t.get("Ticket_Status_Label"))
        unique_priorities = set(t.get("Priority_Level") for t in tickets if t.get("Priority_Level"))
        unique_sites = set(t.get("Site_Label") for t in tickets if t.get("Site_Label"))

        # Normalize diversity score
        max_diversity = 10  # Reasonable maximum
        actual_diversity = len(unique_statuses) + len(unique_priorities) + len(unique_sites)

        return min(actual_diversity / max_diversity, 1.0)

__all__ = ["AdvancedQueryManager"]
