"""add ticket version column

Revision ID: e1a052713de2
Revises: f5f570501dfb
Create Date: 2025-08-15 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e1a052713de2'
down_revision: Union[str, None] = 'f5f570501dfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'Tickets_Master',
        sa.Column('Version', sa.Integer(), nullable=False, server_default='1')
    )
    op.alter_column('Tickets_Master', 'Version', server_default=None)


def downgrade() -> None:
    op.drop_column('Tickets_Master', 'Version')
