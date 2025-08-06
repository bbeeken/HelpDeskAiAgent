"""remove duplicate ticket columns

Revision ID: b88292336e8c
Revises: a3c896922b31
Create Date: 2025-08-06 02:14:28.494207

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b88292336e8c'
down_revision: Union[str, None] = 'a3c896922b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
