"""Deprecated - use :mod:`tools.analytics_reporting` instead."""

from __future__ import annotations

import warnings
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from .analytics_reporting import (
    tickets_by_status,
    open_tickets_by_site,
    sla_breaches,
    open_tickets_by_user,
    tickets_waiting_on_user,
    ticket_trend,
    get_staff_ticket_report,
    AnalyticsManager,
)


__all__ = [
    "tickets_by_status",
    "open_tickets_by_site",
    "sla_breaches",
    "open_tickets_by_user",
    "tickets_waiting_on_user",
    "ticket_trend",
    "get_staff_ticket_report",
    "AnalyticsManager",
]

warnings.warn(
    "tools.analysis_tools is deprecated; use tools.analytics_reporting",
    DeprecationWarning,
    stacklevel=2,
)
