"""Enhanced context retrieval for agent consumption."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
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
from schemas.agent_data import (
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
    # Additional data helpers used by the API endpoints.  Many of these
    # methods only return basic information so the enhanced API does not
    # fail when called during tests.  They can be expanded in the future
    # with richer analytics as needed.
    # ------------------------------------------------------------------

    async def _calculate_user_ticket_statistics(self, user_email: str) -> Dict[str, Any]:
        """Return simple ticket statistics for a user."""
        total_q = select(func.count()).select_from(Ticket).filter(
            Ticket.Ticket_Contact_Email == user_email
        )
        open_q = (
            select(func.count())
            .select_from(Ticket)
            .join(TicketStatus, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
            .filter(
                Ticket.Ticket_Contact_Email == user_email,
                or_(
                    TicketStatus.Label.ilike("%open%"),
                    TicketStatus.Label.ilike("%progress%"),
                ),
            )
        )
        closed_q = (
            select(func.count())
            .select_from(Ticket)
            .join(TicketStatus, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
            .filter(
                Ticket.Ticket_Contact_Email == user_email,
                TicketStatus.Label.ilike("%closed%"),
            )
        )

        total = await self.db.scalar(total_q) or 0
        open_count = await self.db.scalar(open_q) or 0
        closed_count = await self.db.scalar(closed_q) or 0

        # Average resolution time in hours for closed tickets
        result = await self.db.execute(
            select(Ticket.Created_Date, Ticket.Closed_Date).filter(
                Ticket.Ticket_Contact_Email == user_email,
                Ticket.Closed_Date.is_not(None),
            )
        )
        rows = result.all()
        if rows:
            total_seconds = sum(
                (closed - created).total_seconds() for created, closed in rows
            )
            avg_res_hours = total_seconds / len(rows) / 3600
        else:
            avg_res_hours = 0.0

        return {
            "total": total,
            "open": open_count,
            "closed": closed_count,
            "avg_resolution_hours": round(avg_res_hours, 2),
        }

    async def _analyze_user_communication_patterns(self, user_email: str) -> Dict[str, Any]:
        """Return basic communication statistics for a user."""
        result = await self.db.execute(
            select(TicketMessage.Message).filter(
                TicketMessage.SenderUserCode == user_email
            )
        )
        messages = [row[0] for row in result.all()]
        if messages:
            avg_len = sum(len(m or "") for m in messages) / len(messages)
        else:
            avg_len = 0.0
        return {"messages_sent": len(messages), "avg_length": round(avg_len, 1)}

    async def _get_user_technical_context(self, user_email: str) -> Dict[str, Any]:
        """Return assets and sites the user has interacted with."""
        result = await self.db.execute(
            select(
                VTicketMasterExpanded.Asset_ID,
                VTicketMasterExpanded.Asset_Label,
                VTicketMasterExpanded.Site_ID,
                VTicketMasterExpanded.Site_Label,
            ).filter(VTicketMasterExpanded.Ticket_Contact_Email == user_email)
        )
        assets: Dict[int, str] = {}
        sites: Dict[int, str] = {}
        for a_id, a_lbl, s_id, s_lbl in result.all():
            if a_id:
                assets[a_id] = a_lbl
            if s_id:
                sites[s_id] = s_lbl
        return {"assets": list(assets.values()), "sites": list(sites.values())}

    async def _get_user_current_tickets(self, user_email: str) -> List[Dict[str, Any]]:
        """Return currently open tickets for a user."""
        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .join(
                TicketStatus,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                isouter=True,
            )
            .filter(
                VTicketMasterExpanded.Ticket_Contact_Email == user_email,
                or_(
                    TicketStatus.Label.ilike("%open%"),
                    TicketStatus.Label.ilike("%progress%"),
                ),
            )
            .order_by(VTicketMasterExpanded.Created_Date.desc())
        )
        tickets = result.scalars().all()
        return [
            {
                "Ticket_ID": t.Ticket_ID,
                "Subject": t.Subject,
                "Created_Date": t.Created_Date,
                "Status": t.Ticket_Status_Label,
            }
            for t in tickets
        ]

    async def _get_user_recent_resolved_tickets(self, user_email: str) -> List[Dict[str, Any]]:
        """Return recently closed tickets for a user."""
        result = await self.db.execute(
            select(VTicketMasterExpanded)
            .join(
                TicketStatus,
                VTicketMasterExpanded.Ticket_Status_ID == TicketStatus.ID,
                isouter=True,
            )
            .filter(
                VTicketMasterExpanded.Ticket_Contact_Email == user_email,
                TicketStatus.Label.ilike("%closed%"),
            )
            .order_by(VTicketMasterExpanded.Closed_Date.desc())
            .limit(10)
        )
        tickets = result.scalars().all()
        return [
            {
                "Ticket_ID": t.Ticket_ID,
                "Subject": t.Subject,
                "Closed_Date": t.Closed_Date,
            }
            for t in tickets
        ]

    async def _get_asset_complete_info(self, asset_id: int) -> Optional[Dict[str, Any]]:
        asset = await self.db.get(Asset, asset_id)
        if not asset:
            return None
        return {
            "ID": asset.ID,
            "Label": asset.Label,
            "Serial_Number": asset.Serial_Number,
            "Model": asset.Model,
            "Manufacturer": asset.Manufacturer,
            "Site_ID": asset.Site_ID,
        }

    async def _get_site_complete_info(self, site_id: int) -> Optional[Dict[str, Any]]:
        site = await self.db.get(Site, site_id)
        if not site:
            return None
        return {"ID": site.ID, "Label": site.Label, "City": site.City, "State": site.State}

    async def _get_ticket_timeline(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Return simple timeline events based on messages."""
        result = await self.db.execute(
            select(TicketMessage)
            .filter(TicketMessage.Ticket_ID == ticket_id)
            .order_by(TicketMessage.DateTimeStamp)
        )
        msgs = result.scalars().all()
        return [
            {"timestamp": m.DateTimeStamp, "sender": m.SenderUserName, "message": m.Message}
            for m in msgs
        ]

    async def _get_ticket_counts_by_status(self) -> Dict[str, int]:
        result = await self.db.execute(
            select(TicketStatus.Label, func.count(Ticket.Ticket_ID))
            .join(Ticket, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
            .group_by(TicketStatus.Label)
        )
        return {label or "Unknown": count for label, count in result.all()}

    async def _get_ticket_counts_by_priority(self) -> Dict[str, int]:
        result = await self.db.execute(
            select(func.coalesce(Priority.Level, "Unknown"), func.count(Ticket.Ticket_ID))
            .join(Priority, Ticket.Priority_ID == Priority.ID, isouter=True)
            .group_by(Priority.Level)
        )
        return {label: count for label, count in result.all()}

    async def _get_ticket_counts_by_site(self) -> Dict[str, int]:
        result = await self.db.execute(
            select(func.coalesce(Site.Label, "Unknown"), func.count(Ticket.Ticket_ID))
            .join(Site, Ticket.Site_ID == Site.ID, isouter=True)
            .group_by(Site.Label)
        )
        return {label: count for label, count in result.all()}

    async def _get_ticket_counts_by_category(self) -> Dict[str, int]:
        result = await self.db.execute(
            select(func.coalesce(TicketCategory.Label, "Unknown"), func.count(Ticket.Ticket_ID))
            .join(TicketCategory, Ticket.Ticket_Category_ID == TicketCategory.ID, isouter=True)
            .group_by(TicketCategory.Label)
        )
        return {label: count for label, count in result.all()}

    async def _get_all_technician_workloads(self) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
            .group_by(Ticket.Assigned_Email)
        )
        return [
            {"technician": email, "open_tickets": count}
            for email, count in result.all()
            if email
        ]

    async def _get_unassigned_tickets_summary(self) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(Ticket.Ticket_ID, Ticket.Subject, Ticket.Created_Date)
            .filter(Ticket.Assigned_Email.is_(None))
            .order_by(Ticket.Created_Date.desc())
            .limit(20)
        )
        return [
            {"Ticket_ID": tid, "Subject": subj, "Created_Date": created}
            for tid, subj, created in result.all()
        ]

    async def _get_overdue_tickets_summary(self) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        result = await self.db.execute(
            select(Ticket.Ticket_ID, Ticket.Subject, Ticket.Created_Date)
            .join(TicketStatus, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
            .filter(
                or_(TicketStatus.Label.ilike("%open%"), TicketStatus.Label.ilike("%progress%")),
                Ticket.Created_Date < cutoff,
            )
            .order_by(Ticket.Created_Date)
            .limit(20)
        )
        return [
            {"Ticket_ID": tid, "Subject": subj, "Created_Date": created}
            for tid, subj, created in result.all()
        ]

    async def _get_recent_system_activity(self) -> List[Dict[str, Any]]:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await self.db.execute(
            select(Ticket.Ticket_ID, Ticket.Created_Date, Ticket.Subject)
            .filter(Ticket.Created_Date >= since)
            .order_by(Ticket.Created_Date.desc())
        )
        return [
            {"Ticket_ID": tid, "Created_Date": created, "Subject": subj}
            for tid, created, subj in result.all()
        ]

    async def _calculate_system_health(self) -> Dict[str, Any]:
        """Return very simple system health metrics."""
        total = await self.db.scalar(select(func.count(Ticket.Ticket_ID))) or 0
        open_tickets = await self.db.scalar(
            select(func.count())
            .select_from(Ticket)
            .join(TicketStatus, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
            .filter(
                or_(TicketStatus.Label.ilike("%open%"), TicketStatus.Label.ilike("%progress%"))
            )
        ) or 0
        return {
            "total_tickets": total,
            "open_tickets": open_tickets,
            "health": "ok" if open_tickets < total * 0.9 else "warning",
        }
