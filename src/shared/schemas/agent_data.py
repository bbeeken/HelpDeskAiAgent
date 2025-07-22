from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime


class TicketFullContext(BaseModel):
    """Complete ticket data with all related information for agent analysis."""

    # Core ticket data
    ticket: Dict[str, Any]  # Full expanded ticket from VTicketMasterExpanded

    # Related data
    messages: List[Dict[str, Any]]  # All messages chronologically
    attachments: List[Dict[str, Any]]  # All attachment metadata

    # User context
    user_history: Optional[List[Dict[str, Any]]] = None  # User's past tickets
    user_profile: Dict[str, Any]  # User info from Graph API

    # Asset and site context
    asset_details: Optional[Dict[str, Any]]  # Complete asset information
    site_context: Optional[Dict[str, Any]]  # Site info and current state

    # Relationship data
    related_tickets: Optional[List[Dict[str, Any]]] = None  # Same user/asset/site tickets

    # Timeline and metadata
    timeline_events: List[Dict[str, Any]]  # All status changes
    metadata: Dict[str, Any]  # Age, business hours, etc.


class SystemSnapshot(BaseModel):
    """Complete system state for agent situational awareness."""

    # Ticket statistics
    ticket_counts_by_status: Dict[str, int]
    ticket_counts_by_priority: Dict[str, int]
    ticket_counts_by_site: Dict[str, int]
    ticket_counts_by_category: Dict[str, int]

    # Resource status
    technician_workloads: List[Dict[str, Any]]  # Current assignments per tech
    unassigned_tickets: List[Dict[str, Any]]  # Tickets needing assignment
    overdue_tickets: List[Dict[str, Any]]  # SLA breach candidates

    # System health
    recent_activity: List[Dict[str, Any]]  # Last hour of changes
    oncall_status: Optional[Dict[str, Any]]  # Current on-call info
    system_health: Dict[str, Any]  # Performance metrics

    # Timestamp
    snapshot_time: datetime


class UserCompleteProfile(BaseModel):
    """Everything about a user for agent analysis."""

    # Basic information
    basic_info: Dict[str, Any]  # From Azure AD

    # Ticket statistics
    ticket_statistics: Dict[str, Any]  # Counts, averages, patterns

    # Communication patterns
    communication_patterns: Dict[str, Any]  # Response times, styles

    # Technical context
    technical_context: Dict[str, Any]  # Assets, sites, department

    # Current status
    current_tickets: List[Dict[str, Any]]  # All open tickets
    recent_resolved: List[Dict[str, Any]]  # Recently resolved tickets


class AdvancedQuery(BaseModel):
    """Flexible query structure for complex ticket searches."""

    # Text search
    text_search: Optional[str] = None
    search_fields: List[str] = ["Subject", "Ticket_Body"]  # Fields to search

    # Date filters
    date_range: Optional[Dict[str, datetime]] = None  # start, end
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    # Status and priority
    status_filter: Optional[List[str]] = None  # Status labels or IDs
    priority_filter: Optional[List[int]] = None  # Priority IDs

    # Assignment filters
    assigned_to: Optional[List[str]] = None  # Email addresses
    unassigned_only: bool = False

    # Location and asset filters
    site_filter: Optional[List[int]] = None
    asset_filter: Optional[List[int]] = None
    category_filter: Optional[List[int]] = None

    # User filters
    contact_email: Optional[List[str]] = None
    contact_name: Optional[str] = None

    # Custom conditions
    custom_filters: Dict[str, Any] = {}

    # Result control
    sort_by: List[Dict[str, str]] = [{"field": "Created_Date", "direction": "desc"}]
    limit: int = 100
    offset: int = 0

    # Include related data
    include_messages: bool = False
    include_attachments: bool = False
    include_user_context: bool = False

    @field_validator("limit", "offset")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be >= 0")
        return v


class QueryResult(BaseModel):
    """Rich query results with metadata."""

    tickets: List[Dict[str, Any]]  # Matching tickets with requested context
    total_count: int  # Total matches (for pagination)

    # Query metadata
    execution_time_ms: float
    query_complexity: str  # "simple", "medium", "complex"
    cache_used: bool

    # Result analysis
    aggregations: Dict[str, Any]  # Breakdowns by category, priority, etc.
    result_quality: Dict[str, Any]  # Relevance scores, data completeness


class OperationResult(BaseModel):
    """Enhanced operation result with full context."""

    success: bool
    action_taken: str

    # State information
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None

    # Affected entities
    affected_tickets: List[int] = []
    affected_users: List[str] = []

    # Execution details
    execution_metadata: Dict[str, Any]

    # Error information (if failed)
    error_details: Optional[Dict[str, Any]] = None

    # Rollback information
    rollback_available: bool = False
    rollback_instructions: Optional[Dict[str, Any]] = None


class ValidationResult(BaseModel):
    """Pre-execution validation results."""

    is_valid: bool
    confidence: float  # 0.0 to 1.0

    # Issues found
    blocking_errors: List[str] = []  # Prevent execution
    warnings: List[str] = []  # Allow execution but flag

    # Context and recommendations
    context_notes: List[str] = []
    recommendations: List[str] = []

    # Impact assessment
    estimated_impact: Dict[str, Any]
    affected_entities: List[str] = []
