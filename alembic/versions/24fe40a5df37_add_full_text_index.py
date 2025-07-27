"""add full text search index

Revision ID: 24fe40a5df37
Revises: f5f570501dfb
Create Date: 2025-07-30 00:00:00
"""

from typing import Sequence, Union
from alembic import op

revision: str = '24fe40a5df37'
down_revision: Union[str, None] = 'f5f570501dfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tickets_master_fts ON \"Tickets_Master\" USING GIN (to_tsvector('english', coalesce(\"Subject\", '') || ' ' || coalesce(\"Ticket_Body\", '')))"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    op.execute("DROP INDEX IF EXISTS ix_tickets_master_fts")
