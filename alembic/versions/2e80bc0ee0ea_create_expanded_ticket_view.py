"""create expanded ticket view

Revision ID: 2e80bc0ee0ea
Revises: 7bee13849318
Create Date: 2025-07-03 04:12:26.131518

"""
from typing import Sequence, Union

from alembic import op
from db.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL


# revision identifiers, used by Alembic.
revision: str = '2e80bc0ee0ea'
down_revision: Union[str, None] = '7bee13849318'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREATE_VIEW_SQL = CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL


def upgrade() -> None:
    op.execute(CREATE_VIEW_SQL)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
