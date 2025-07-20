"""Enhanced context retrieval for agent consumption."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.models import (
    Ticket,
    VTicketMasterExpanded,
    TicketMessage,
    TicketAttachment,
    Asset,
    Site,
    TicketCategory,
    TicketStatus,
    Priority,
)
from src.shared.schemas.agent_data import (
    TicketFullContext, SystemSnapshot, UserCompleteProfile
)
from .user_services import UserManager
from .analytics_reporting import AnalyticsManager

logger = logging.getLogger(__name__)


class EnhancedContextManager:
    """Provides rich contextual data for AI agent consumption."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_manager = UserManager()
        self.analytics = AnalyticsManager(db)

    async def get_ticket_full_context(
        self,
        ticket_id: int,
        include_deep_history: bool = True
    ) -> TicketFullContext:
        """Get comprehensive ticket context for agent analysis."""

        # Get base ticket with expanded view
        ticket = await self.db.get(VTicketMasterExpanded, ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Convert to dict for JSON serialization
        ticket_dict = {
            column.name: getattr(ticket, column.name)
            for column in ticket.__table__.columns
        }

        # Get all related data in parallel
        messages = await self._get_ticket_messages(ticket_id)
        attachments = await self._get_ticket_attachments(ticket_id)
        user_history = await self._get_user_ticket_history(
            ticket.Ticket_Contact_Email,
            limit=50 if include_deep_history else 10
        )
        user_profile = await self.user_manager.get_user_by_email(ticket.Ticket_Contact_Email)

        # Asset and site context
        asset_details = None
        if ticket.Asset_ID:
            asset_details = await self._get_asset_complete_info(ticket.Asset_ID)

        site_context = None
        if ticket.Site_ID:
            site_context = await self._get_site_complete_info(ticket.Site_ID)

        # Related tickets
        related_tickets = await self._find_related_tickets(ticket)

        # Timeline events
        timeline_events = await self._get_ticket_timeline(ticket_id)

        # Generate metadata
        metadata = await self._generate_ticket_metadata(ticket)

        return TicketFullContext(
            ticket=ticket_dict,
            messages=messages,
            attachments=attachments,
            user_history=user_history,
            user_profile=user_profile,
            asset_details=asset_details,
            site_context=site_context,
            related_tickets=related_tickets,
            timeline_events=timeline_events,
            metadata=metadata
        )

    async def get_system_snapshot(self) -> SystemSnapshot:
        """Get comprehensive system state snapshot."""

        # Get ticket counts by various dimensions
        status_counts = await self._get_ticket_counts_by_status()
        priority_counts = await self._get_ticket_counts_by_priority()
        site_counts = await self._get_ticket_counts_by_site()
        category_counts = await self._get_ticket_counts_by_category()

        # Get technician workloads
        tech_workloads = await self._get_all_technician_workloads()

        # Get critical tickets
        unassigned_tickets = await self._get_unassigned_tickets_summary()
        overdue_tickets = await self._get_overdue_tickets_summary()

        # Get recent activity
        recent_activity = await self._get_recent_system_activity()

        # Get on-call status
        oncall_status = await self.user_manager.get_current_oncall(self.db)
        oncall_dict = None
        if oncall_status:
            oncall_dict = {
                "user_email": oncall_status.user_email,
                "start_time": oncall_status.start_time,
                "end_time": oncall_status.end_time
            }

        # Generate system health metrics
        system_health = await self._calculate_system_health()

        return SystemSnapshot(
            ticket_counts_by_status=status_counts,
            ticket_counts_by_priority=priority_counts,
            ticket_counts_by_site=site_counts,
            ticket_counts_by_category=category_counts,
            technician_workloads=tech_workloads,
            unassigned_tickets=unassigned_tickets,
            overdue_tickets=overdue_tickets,
            recent_activity=recent_activity,
            oncall_status=oncall_dict,
            system_health=system_health,
            snapshot_time=datetime.now(timezone.utc)
        )

    async def get_user_complete_profile(self, user_email: str) -> UserCompleteProfile:
        """Get comprehensive user profile for agent analysis."""

        # Basic user info from Azure AD
        basic_info = await self.user_manager.get_user_by_email(user_email)

        # Calculate ticket statistics
        ticket_stats = await self._calculate_user_ticket_statistics(user_email)

        # Analyze communication patterns
        comm_patterns = await self._analyze_user_communication_patterns(user_email)

        # Get technical context
        tech_context = await self._get_user_technical_context(user_email)

        # Get current and recent tickets
        current_tickets = await self._get_user_current_tickets(user_email)
        recent_resolved = await self._get_user_recent_resolved_tickets(user_email)

        return UserCompleteProfile(
            basic_info=basic_info,
            ticket_statistics=ticket_stats,
            communication_patterns=comm_patterns,
            technical_context=tech_context,
            current_tickets=current_tickets,
            recent_resolved=recent_resolved
        )

    # Helper methods for data gathering
    async def _get_ticket_messages(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get all messages for a ticket."""
        result = await self.db.execute(
            select(TicketMessage)
            .filter(TicketMessage.Ticket_ID == ticket_id)
            .order_by(TicketMessage.DateTimeStamp)
        )
        messages = result.scalars().all()

        return [
            {
                "ID": msg.ID,
                "Message": msg.Message,
                "SenderUserCode": msg.SenderUserCode,
                "SenderUserName": msg.SenderUserName,
                "DateTimeStamp": msg.DateTimeStamp,
                "message_length": len(msg.Message) if msg.Message else 0,
                "is_technician": "@" in (msg.SenderUserCode or "")
            }
            for msg in messages
        ]

    async def _get_ticket_attachments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get all attachments for a ticket."""
        result = await self.db.execute(
            select(TicketAttachment)
            .filter(TicketAttachment.Ticket_ID == ticket_id)
        )
        attachments = result.scalars().all()

        return [
            {
                "ID": att.ID,
                "Name": att.Name,
                "WebURl": att.WebURl,
                "UploadDateTime": att.UploadDateTime,
                "file_size_estimate": len(att.Name) * 1024  # Rough estimate
            }
            for att in attachments
        ]

    async def _get_user_ticket_history(
        self, user_email: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get user's ticket history."""
        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .filter(VTicketMasterExpanded.Ticket_Contact_Email == user_email)
            .order_by(VTicketMasterExpanded.Created_Date.desc())
            .limit(limit)
        )
        tickets = result.scalars().all()

        return [
            {
                "Ticket_ID": t.Ticket_ID,
                "Subject": t.Subject,
                "Created_Date": t.Created_Date,
                "Ticket_Status_Label": t.Ticket_Status_Label,
                "Priority_Level": t.Priority_Level,
                "Assigned_Name": t.Assigned_Name,
                "resolution_time_hours": self._calculate_resolution_time(t)
            }
            for t in tickets
        ]

    async def _find_related_tickets(self, ticket) -> List[Dict[str, Any]]:
        """Find tickets related by user, asset, or site."""
        conditions = []

        # Same user
        if ticket.Ticket_Contact_Email:
            conditions.append(
                VTicketMasterExpanded.Ticket_Contact_Email == ticket.Ticket_Contact_Email
            )

        # Same asset
        if ticket.Asset_ID:
            conditions.append(VTicketMasterExpanded.Asset_ID == ticket.Asset_ID)

        # Same site
        if ticket.Site_ID:
            conditions.append(VTicketMasterExpanded.Site_ID == ticket.Site_ID)

        if not conditions:
            return []

        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .filter(
                and_(
                    VTicketMasterExpanded.Ticket_ID != ticket.Ticket_ID,
                    or_(*conditions)
                )
            )
            .order_by(VTicketMasterExpanded.Created_Date.desc())
            .limit(20)
        )

        related = result.scalars().all()
        return [
            {
                "Ticket_ID": t.Ticket_ID,
                "Subject": t.Subject,
                "Created_Date": t.Created_Date,
                "relationship_type": self._determine_relationship_type(ticket, t)
            }
            for t in related
        ]

    async def _generate_ticket_metadata(self, ticket) -> Dict[str, Any]:
        """Generate useful metadata about the ticket."""
        now = datetime.now(timezone.utc)
        created = ticket.Created_Date

        if created:
            age_total = now - created
            age_minutes = age_total.total_seconds() / 60

            # Calculate business hours age (rough estimate)
            business_hours_age = self._calculate_business_hours_age(created, now)
        else:
            age_minutes = 0
            business_hours_age = 0

        return {
            "created_timestamp": created,
            "last_modified": ticket.LastModified,
            "age_minutes": age_minutes,
            "age_hours": age_minutes / 60,
            "age_days": age_minutes / (60 * 24),
            "business_hours_age_hours": business_hours_age,
            "is_overdue": age_minutes > (24 * 60),  # Simple 24-hour SLA
            "priority_text": self._priority_id_to_text(ticket.Priority_ID),
            "complexity_estimate": self._estimate_ticket_complexity(ticket)
        }

    # Additional helper methods...
    def _calculate_resolution_time(self, ticket) -> Optional[float]:
        """Calculate resolution time in hours."""
        if ticket.Closed_Date and ticket.Created_Date:
            delta = ticket.Closed_Date - ticket.Created_Date
            return delta.total_seconds() / 3600
        return None

    def _determine_relationship_type(self, base_ticket, related_ticket) -> str:
        """Determine how tickets are related."""
        if base_ticket.Ticket_Contact_Email == related_ticket.Ticket_Contact_Email:
            return "same_user"
        elif base_ticket.Asset_ID == related_ticket.Asset_ID:
            return "same_asset"
        elif base_ticket.Site_ID == related_ticket.Site_ID:
            return "same_site"
        return "unknown"

    def _calculate_business_hours_age(self, start: datetime, end: datetime) -> float:
        """Rough calculation of business hours between two dates."""
        # Simplified: assume 8-hour business days, M-F
        total_hours = (end - start).total_seconds() / 3600
        # Rough approximation: 40 business hours per week
        return total_hours * (40 / 168)  # 168 hours in a week

    def _priority_id_to_text(self, priority_id: Optional[int]) -> str:
        """Convert priority ID to text."""
        mapping = {1: "Critical", 2: "High", 3: "Medium", 4: "Low"}
        return mapping.get(priority_id or 3, "Medium")

    def _estimate_ticket_complexity(self, ticket) -> str:
        """Rough complexity estimate based on available data."""
        subject_length = len(ticket.Subject or "")
        body_length = len(ticket.Ticket_Body or "")

        if body_length > 500 or subject_length > 100:
            return "high"
        elif body_length > 200 or subject_length > 50:
            return "medium"
        else:
            return "low"

    # ------------------------------------------------------------------
    # Asset and site context helpers
    async def _get_asset_complete_info(self, asset_id: int) -> Dict[str, Any]:
        """Get complete asset information."""
        asset = await self.db.get(Asset, asset_id)
        if not asset:
            return {}

        # Get ticket count for this asset
        result = await self.db.execute(
            select(func.count(VTicketMasterExpanded.Ticket_ID))
            .filter(VTicketMasterExpanded.Asset_ID == asset_id)
        )
        ticket_count = result.scalar() or 0

        # Get recent tickets for this asset
        recent_result = await self.db.execute(
            select(VTicketMasterExpanded)
            .filter(VTicketMasterExpanded.Asset_ID == asset_id)
            .order_by(VTicketMasterExpanded.Created_Date.desc())
            .limit(5)
        )
        recent_tickets = recent_result.scalars().all()

        return {
            "asset_id": asset.ID,
            "label": asset.Label,
            "category_id": asset.Asset_Category_ID,
            "serial_number": asset.Serial_Number,
            "model": asset.Model,
            "manufacturer": asset.Manufacturer,
            "site_id": asset.Site_ID,
            "total_tickets": ticket_count,
            "recent_tickets": [
                {
                    "ticket_id": t.Ticket_ID,
                    "subject": t.Subject,
                    "created_date": t.Created_Date,
                    "status": t.Ticket_Status_Label,
                }
                for t in recent_tickets
            ],
        }

    async def _get_site_complete_info(self, site_id: int) -> Dict[str, Any]:
        """Get complete site information."""
        site = await self.db.get(Site, site_id)
        if not site:
            return {}

        # Get total tickets for this site
        result = await self.db.execute(
            select(func.count(VTicketMasterExpanded.Ticket_ID))
            .filter(VTicketMasterExpanded.Site_ID == site_id)
        )
        total_tickets = result.scalar() or 0

        # Get open tickets for this site
        open_result = await self.db.execute(
            select(func.count(VTicketMasterExpanded.Ticket_ID))
            .join(
                TicketStatus,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                isouter=True,
            )
            .filter(
                and_(
                    VTicketMasterExpanded.Site_ID == site_id,
                    or_(
                        TicketStatus.Label.ilike("%open%"),
                        TicketStatus.Label.ilike("%progress%"),
                    ),
                )
            )
        )
        open_tickets = open_result.scalar() or 0

        return {
            "site_id": site.ID,
            "label": site.Label,
            "city": site.City,
            "state": site.State,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "ticket_health": "good" if open_tickets < 5 else "attention_needed",
        }

    async def _get_ticket_timeline(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get timeline of events for a ticket."""
        messages_result = await self.db.execute(
            select(TicketMessage)
            .filter(TicketMessage.Ticket_ID == ticket_id)
            .order_by(TicketMessage.DateTimeStamp)
        )
        messages = messages_result.scalars().all()

        timeline = []
        for msg in messages:
            timeline.append(
                {
                    "type": "message",
                    "timestamp": msg.DateTimeStamp,
                    "actor": msg.SenderUserName or msg.SenderUserCode,
                    "description": (
                        f"Added message: {msg.Message[:100]}..."
                        if len(msg.Message or "") > 100
                        else msg.Message
                    ),
                    "details": {"message_id": msg.ID},
                }
            )

        return timeline

    # ------------------------------------------------------------------
    # System snapshot helpers
    async def _get_ticket_counts_by_status(self) -> Dict[str, int]:
        """Get ticket counts grouped by status."""
        result = await self.db.execute(
            select(TicketStatus.Label, func.count(Ticket.Ticket_ID))
            .join(Ticket, TicketStatus.ID == Ticket.Ticket_Status_ID, isouter=True)
            .group_by(TicketStatus.Label)
        )
        return {row[0] or "Unknown": row[1] for row in result.all()}

    async def _get_ticket_counts_by_priority(self) -> Dict[str, int]:
        """Get ticket counts grouped by priority."""
        result = await self.db.execute(
            select(
                VTicketMasterExpanded.Priority_Level,
                func.count(VTicketMasterExpanded.Ticket_ID),
            )
            .group_by(VTicketMasterExpanded.Priority_Level)
        )
        return {row[0] or "Medium": row[1] for row in result.all()}

    async def _get_ticket_counts_by_site(self) -> Dict[str, int]:
        """Get ticket counts grouped by site."""
        result = await self.db.execute(
            select(
                VTicketMasterExpanded.Site_Label,
                func.count(VTicketMasterExpanded.Ticket_ID),
            )
            .group_by(VTicketMasterExpanded.Site_Label)
        )
        return {row[0] or "Unknown": row[1] for row in result.all()}

    async def _get_ticket_counts_by_category(self) -> Dict[str, int]:
        """Get ticket counts grouped by category."""
        result = await self.db.execute(
            select(
                VTicketMasterExpanded.Ticket_Category_Label,
                func.count(VTicketMasterExpanded.Ticket_ID),
            )
            .group_by(VTicketMasterExpanded.Ticket_Category_Label)
        )
        return {row[0] or "Unknown": row[1] for row in result.all()}

    async def _get_all_technician_workloads(self) -> List[Dict[str, Any]]:
        """Get workload for all technicians."""
        result = await self.db.execute(
            select(
                VTicketMasterExpanded.Assigned_Email,
                VTicketMasterExpanded.Assigned_Name,
                func.count(VTicketMasterExpanded.Ticket_ID),
            )
            .join(
                TicketStatus,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                isouter=True,
            )
            .filter(
                and_(
                    VTicketMasterExpanded.Assigned_Email.is_not(None),
                    or_(
                        TicketStatus.Label.ilike("%open%"),
                        TicketStatus.Label.ilike("%progress%"),
                    ),
                )
            )
            .group_by(
                VTicketMasterExpanded.Assigned_Email,
                VTicketMasterExpanded.Assigned_Name,
            )
        )

        return [
            {
                "email": row[0],
                "name": row[1],
                "open_tickets": row[2],
                "workload_status": "heavy" if row[2] > 10 else "normal",
            }
            for row in result.all()
        ]

    async def _get_unassigned_tickets_summary(self) -> List[Dict[str, Any]]:
        """Get summary of unassigned tickets."""
        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .join(
                TicketStatus,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                isouter=True,
            )
            .filter(
                and_(
                    VTicketMasterExpanded.Assigned_Email.is_(None),
                    or_(
                        TicketStatus.Label.ilike("%open%"),
                        TicketStatus.Label.ilike("%progress%"),
                    ),
                )
            )
            .order_by(VTicketMasterExpanded.Created_Date.desc())
            .limit(10)
        )

        tickets = result.scalars().all()
        return [
            {
                "ticket_id": t.Ticket_ID,
                "subject": t.Subject,
                "priority": t.Priority_Level,
                "created_date": t.Created_Date,
                "age_hours": (
                    (datetime.now(timezone.utc) - t.Created_Date).total_seconds()
                    / 3600
                    if t.Created_Date
                    else 0
                ),
            }
            for t in tickets
        ]

    async def _get_overdue_tickets_summary(self) -> List[Dict[str, Any]]:
        """Get summary of overdue tickets."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .join(
                TicketStatus,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                isouter=True,
            )
            .filter(
                and_(
                    VTicketMasterExpanded.Created_Date < cutoff,
                    or_(
                        TicketStatus.Label.ilike("%open%"),
                        TicketStatus.Label.ilike("%progress%"),
                    ),
                )
            )
            .order_by(VTicketMasterExpanded.Created_Date.asc())
            .limit(10)
        )

        tickets = result.scalars().all()
        return [
            {
                "ticket_id": t.Ticket_ID,
                "subject": t.Subject,
                "assigned_to": t.Assigned_Name,
                "created_date": t.Created_Date,
                "days_overdue": (
                    (datetime.now(timezone.utc) - t.Created_Date).days
                    if t.Created_Date
                    else 0
                ),
            }
            for t in tickets
        ]

    async def _get_recent_system_activity(self) -> List[Dict[str, Any]]:
        """Get recent system activity."""
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .filter(VTicketMasterExpanded.Created_Date >= recent_cutoff)
            .order_by(VTicketMasterExpanded.Created_Date.desc())
            .limit(20)
        )

        tickets = result.scalars().all()
        return [
            {
                "type": "ticket_created",
                "ticket_id": t.Ticket_ID,
                "subject": t.Subject,
                "timestamp": t.Created_Date,
                "user": t.Ticket_Contact_Name,
            }
            for t in tickets
        ]

    async def _calculate_system_health(self) -> Dict[str, Any]:
        """Calculate overall system health metrics."""
        last_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        # Get recent ticket count
        recent_result = await self.db.execute(
            select(func.count(Ticket.Ticket_ID)).filter(Ticket.Created_Date >= last_24h)
        )
        recent_count = recent_result.scalar() or 0

        # Get open ticket count
        open_result = await self.db.execute(
            select(func.count(VTicketMasterExpanded.Ticket_ID))
            .join(
                TicketStatus,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                isouter=True,
            )
            .filter(
                or_(
                    TicketStatus.Label.ilike("%open%"),
                    TicketStatus.Label.ilike("%progress%"),
                )
            )
        )
        open_count = open_result.scalar() or 0

        # Calculate health score
        health_score = max(0, 100 - (recent_count * 2) - (open_count * 1))

        return {
            "score": health_score,
            "status": (
                "healthy"
                if health_score > 80
                else "degraded"
                if health_score > 60
                else "critical"
            ),
            "recent_ticket_volume": recent_count,
            "open_tickets": open_count,
            "last_calculated": datetime.now(timezone.utc),
        }

    # ------------------------------------------------------------------
    # User profile helpers - robust implementations with error handling
    async def _calculate_user_ticket_statistics(self, user_email: str) -> Dict[str, Any]:
        """Calculate ticket statistics for a user with error handling."""
        try:
            # Total tickets
            total_result = await self.db.execute(
                select(func.count(VTicketMasterExpanded.Ticket_ID)).filter(
                    VTicketMasterExpanded.Ticket_Contact_Email == user_email
                )
            )
            total_tickets = total_result.scalar() or 0

            # Open tickets
            open_result = await self.db.execute(
                select(func.count(VTicketMasterExpanded.Ticket_ID))
                .join(
                    TicketStatus,
                    VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                    isouter=True,
                )
                .filter(
                    and_(
                        VTicketMasterExpanded.Ticket_Contact_Email == user_email,
                        or_(
                            TicketStatus.Label.ilike("%open%"),
                            TicketStatus.Label.ilike("%progress%"),
                        ),
                    )
                )
            )
            open_tickets = open_result.scalar() or 0

            # Calculate average resolution time for closed tickets
            resolution_result = await self.db.execute(
                select(VTicketMasterExpanded.Created_Date, VTicketMasterExpanded.Closed_Date)
                .filter(
                    and_(
                        VTicketMasterExpanded.Ticket_Contact_Email == user_email,
                        VTicketMasterExpanded.Closed_Date.is_not(None),
                    )
                )
            )
            rows = resolution_result.all()
            
            avg_resolution_hours = 0.0
            if rows:
                total_seconds = sum(
                    (closed - created).total_seconds() 
                    for created, closed in rows 
                    if created and closed
                )
                avg_resolution_hours = total_seconds / len(rows) / 3600

            return {
                "total_tickets": total_tickets,
                "open_tickets": open_tickets,
                "closed_tickets": total_tickets - open_tickets,
                "avg_resolution_hours": round(avg_resolution_hours, 2),
                "ticket_frequency": "high" if total_tickets > 20 else "normal",
            }
        except Exception as e:
            logger.error(f"Error calculating user ticket statistics for {user_email}: {e}")
            return {
                "total_tickets": 0,
                "open_tickets": 0,
                "closed_tickets": 0,
                "avg_resolution_hours": 0.0,
                "ticket_frequency": "normal",
            }

    async def _analyze_user_communication_patterns(self, user_email: str) -> Dict[str, Any]:
        """Analyze user's communication patterns with error handling."""
        try:
            result = await self.db.execute(
                select(TicketMessage)
                .filter(TicketMessage.SenderUserCode == user_email)
                .order_by(TicketMessage.DateTimeStamp.desc())
                .limit(50)
            )
            messages = result.scalars().all()

            if not messages:
                return {
                    "message_count": 0,
                    "avg_message_length": 0.0,
                    "communication_style": "minimal",
                    "last_message_date": None,
                }

            message_lengths = [len(msg.Message or "") for msg in messages]
            avg_length = sum(message_lengths) / len(message_lengths) if message_lengths else 0

            return {
                "message_count": len(messages),
                "avg_message_length": round(avg_length, 1),
                "communication_style": "detailed" if avg_length > 200 else "concise",
                "last_message_date": messages[0].DateTimeStamp if messages else None,
            }
        except Exception as e:
            logger.error(f"Error analyzing communication patterns for {user_email}: {e}")
            return {
                "message_count": 0,
                "avg_message_length": 0.0,
                "communication_style": "unknown",
                "last_message_date": None,
            }

    async def _get_user_technical_context(self, user_email: str) -> Dict[str, Any]:
        """Get technical context for a user with error handling."""
        try:
            result = await self.db.execute(
                select(
                    VTicketMasterExpanded.Site_Label,
                    VTicketMasterExpanded.Asset_Label,
                    func.count(VTicketMasterExpanded.Ticket_ID),
                )
                .filter(VTicketMasterExpanded.Ticket_Contact_Email == user_email)
                .group_by(
                    VTicketMasterExpanded.Site_Label,
                    VTicketMasterExpanded.Asset_Label,
                )
                .order_by(func.count(VTicketMasterExpanded.Ticket_ID).desc())
                .limit(10)
            )

            associations = result.all()
            sites = list({row[0] for row in associations if row[0]})
            assets = list({row[1] for row in associations if row[1]})

            return {
                "primary_sites": sites,
                "common_assets": assets,
                "technical_expertise": "high" if len(associations) > 5 else "normal",
            }
        except Exception as e:
            logger.error(f"Error getting technical context for {user_email}: {e}")
            return {
                "primary_sites": [],
                "common_assets": [],
                "technical_expertise": "normal",
            }

    async def _get_user_current_tickets(self, user_email: str) -> List[Dict[str, Any]]:
        """Get user's current open tickets with error handling."""
        try:
            result = await self.db.execute(
                select(VTicketMasterExpanded)
                .join(
                    TicketStatus,
                    VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                    isouter=True,
                )
                .filter(
                    and_(
                        VTicketMasterExpanded.Ticket_Contact_Email == user_email,
                        or_(
                            TicketStatus.Label.ilike("%open%"),
                            TicketStatus.Label.ilike("%progress%"),
                        ),
                    )
                )
                .order_by(VTicketMasterExpanded.Created_Date.desc())
            )

            tickets = result.scalars().all()
            return [
                {
                    "ticket_id": t.Ticket_ID,
                    "subject": t.Subject,
                    "status": t.Ticket_Status_Label,
                    "priority": t.Priority_Level,
                    "assigned_to": t.Assigned_Name,
                    "created_date": t.Created_Date,
                }
                for t in tickets
            ]
        except Exception as e:
            logger.error(f"Error getting current tickets for {user_email}: {e}")
            return []

    async def _get_user_recent_resolved_tickets(self, user_email: str) -> List[Dict[str, Any]]:
        """Get user's recently resolved tickets with error handling."""
        try:
            result = await self.db.execute(
                select(VTicketMasterExpanded)
                .join(
                    TicketStatus,
                    VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                    isouter=True,
                )
                .filter(
                    and_(
                        VTicketMasterExpanded.Ticket_Contact_Email == user_email,
                        or_(
                            TicketStatus.Label.ilike("%closed%"),
                            TicketStatus.Label.ilike("%resolved%"),
                        ),
                    )
                )
                .order_by(VTicketMasterExpanded.Closed_Date.desc())
                .limit(10)
            )

            tickets = result.scalars().all()
            return [
                {
                    "ticket_id": t.Ticket_ID,
                    "subject": t.Subject,
                    "resolution": getattr(t, 'Resolution', None),
                    "closed_date": t.Closed_Date,
                    "resolution_time_hours": self._calculate_resolution_time(t),
                }
                for t in tickets
            ]
        except Exception as e:
            logger.error(f"Error getting recent resolved tickets for {user_email}: {e}")
            return []
