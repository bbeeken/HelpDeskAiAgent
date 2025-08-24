"""add default constraint for Ticket_Messages.DateTimeStamp

Revision ID: 3df7999fa708
Revises: d19ef6e3f1d9
Create Date: 2025-10-20 00:00:00
"""

from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]

revision: str = "3df7999fa708"
down_revision: Union[str, None] = "d19ef6e3f1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mssql":
        return

    op.execute(
        """
        ALTER TABLE [dbo].[Ticket_Messages]
        ADD CONSTRAINT DF_Ticket_Messages_DateTimeStamp
            DEFAULT (GETDATE()) FOR [DateTimeStamp]
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mssql":
        return

    op.execute(
        """
        ALTER TABLE [dbo].[Ticket_Messages]
        DROP CONSTRAINT DF_Ticket_Messages_DateTimeStamp
        """
    )
