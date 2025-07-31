"""update expanded ticket view

Revision ID: 237fcdff6dee
Revises: e1a052713de2
Create Date: 2025-09-30 00:00:00
"""

from typing import Sequence, Union
from alembic import op  # type: ignore[attr-defined]
from src.core.repositories.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL

revision: str = "237fcdff6dee"
down_revision: Union[str, None] = "e1a052713de2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
    op.execute(CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
