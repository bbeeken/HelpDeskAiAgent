"""rename priority level column to label

Revision ID: c1b9e2b8163b
Revises: b88292336e8c, 237fcdff6dee
Create Date: 2025-10-08 00:00:00
"""

from typing import Sequence, Union
from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


revision: str = "c1b9e2b8163b"
down_revision: Union[str, Sequence[str], None] = (
    "b88292336e8c",
    "237fcdff6dee",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("Priority_Levels", "Level", new_column_name="Label")
    op.alter_column("Priority_Levels", "Label", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    op.alter_column("Priority_Levels", "Label", existing_type=sa.String(), nullable=True)
    op.alter_column("Priority_Levels", "Label", new_column_name="Level")

