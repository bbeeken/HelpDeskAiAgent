"""add missing ticket columns

Revision ID: a3c896922b31
Revises: e1a052713de2
Create Date: 2025-09-01 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3c896922b31'
down_revision: Union[str, None] = 'e1a052713de2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'Tickets_Master',
        sa.Column('Most_Recent_Service_Scheduled_ID', sa.Integer(), nullable=True)
    )
    op.add_column(
        'Tickets_Master',
        sa.Column('Watchers', sa.Text(), nullable=True)
    )
    op.add_column(
        'Tickets_Master',
        sa.Column('MetaData', sa.Text(), nullable=True)
    )
    op.add_column(
        'Tickets_Master',
        sa.Column('ValidFrom', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'Tickets_Master',
        sa.Column('ValidTo', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('Tickets_Master', 'ValidTo')
    op.drop_column('Tickets_Master', 'ValidFrom')
    op.drop_column('Tickets_Master', 'MetaData')
    op.drop_column('Tickets_Master', 'Watchers')
    op.drop_column('Tickets_Master', 'Most_Recent_Service_Scheduled_ID')

