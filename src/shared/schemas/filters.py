from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Any

from sqlalchemy import and_


@dataclass
class AdvancedFilters:
    """Optional filters with additional capabilities."""

    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    status_ids: Optional[List[str]] = None
    site_ids: Optional[List[int]] = None
    assigned: Optional[bool] = None
    sort: Optional[Sequence[str]] = None


def apply_advanced_filters(query, filters: AdvancedFilters, model: Any):
    """Apply ``AdvancedFilters`` to a SQLAlchemy ``Select`` query."""

    conditions = []
    if filters.created_from and hasattr(model, "Created_Date"):
        conditions.append(getattr(model, "Created_Date") >= filters.created_from)
    if filters.created_to and hasattr(model, "Created_Date"):
        conditions.append(getattr(model, "Created_Date") <= filters.created_to)
    if filters.status_ids and hasattr(model, "Ticket_Status_ID"):
        conditions.append(getattr(model, "Ticket_Status_ID").in_(filters.status_ids))
    if filters.site_ids and hasattr(model, "Site_ID"):
        conditions.append(getattr(model, "Site_ID").in_(filters.site_ids))
    if filters.assigned is not None and hasattr(model, "Assigned_Email"):
        col = getattr(model, "Assigned_Email")
        conditions.append(col.is_not(None) if filters.assigned else col.is_(None))

    if conditions:
        query = query.filter(and_(*conditions))

    sort_values = filters.sort
    if sort_values:
        if isinstance(sort_values, str):
            sort_values = [sort_values]
        order_columns = []
        for s in sort_values:
            direction = "asc"
            column = s
            if s.startswith("-"):
                column = s[1:]
                direction = "desc"
            elif " " in s:
                column, dir_part = s.rsplit(" ", 1)
                if dir_part.lower() in {"asc", "desc"}:
                    direction = dir_part.lower()
            if hasattr(model, column):
                attr = getattr(model, column)
                order_columns.append(attr.desc() if direction == "desc" else attr.asc())
        if order_columns:
            query = query.order_by(*order_columns)

    return query

