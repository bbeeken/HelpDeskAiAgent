"""remove RV, ValidFrom, ValidTo from Tickets_Master

Revision ID: d19ef6e3f1d9
Revises: b88292336e8c
Create Date: 2025-10-10 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d19ef6e3f1d9"
down_revision: Union[str, None] = "b88292336e8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("Tickets_Master", "RV")
    op.drop_column("Tickets_Master", "ValidFrom")
    op.drop_column("Tickets_Master", "ValidTo")


def downgrade() -> None:
    op.add_column("Tickets_Master", sa.Column("RV", sa.String(), nullable=True))
    op.add_column("Tickets_Master", sa.Column("ValidFrom", sa.DateTime(), nullable=True))
    op.add_column("Tickets_Master", sa.Column("ValidTo", sa.DateTime(), nullable=True))

