"""Add timezone awareness to datetime columns.

Revision ID: f5f570501dfb
Revises: 2e80bc0ee0ea
Create Date: 2025-07-20 21:22:34

This migration converts various ``DateTime`` fields to ``TIMESTAMPTZ`` when
executed on PostgreSQL. SQLite lacks true timezone support, so in that case the
operation is a no-op and the application continues to store naive UTC
datetimes.

Affected columns include:

* ``Tickets_Master.Created_Date``
* ``Tickets_Master.Closed_Date``
* ``Tickets_Master.LastModified``
* ``Ticket_Messages.DateTimeStamp``
* ``Ticket_Attachments.UploadDateTime``
* ``OnCall_Shifts.start_time``
* ``OnCall_Shifts.end_time``
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f5f570501dfb'
down_revision: Union[str, None] = '2e80bc0ee0ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade database schema."""

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite and other dialects remain unchanged; application handles UTC.
        return

    op.execute(
        "ALTER TABLE Tickets_Master ALTER COLUMN Created_Date"
        " TYPE TIMESTAMPTZ USING Created_Date AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE Tickets_Master ALTER COLUMN Closed_Date"
        " TYPE TIMESTAMPTZ USING Closed_Date AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE Tickets_Master ALTER COLUMN LastModified"
        " TYPE TIMESTAMPTZ USING LastModified AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE Ticket_Messages ALTER COLUMN DateTimeStamp"
        " TYPE TIMESTAMPTZ USING DateTimeStamp AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE Ticket_Attachments ALTER COLUMN UploadDateTime"
        " TYPE TIMESTAMPTZ USING UploadDateTime AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE OnCall_Shifts ALTER COLUMN start_time"
        " TYPE TIMESTAMPTZ USING start_time AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE OnCall_Shifts ALTER COLUMN end_time"
        " TYPE TIMESTAMPTZ USING end_time AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    """Revert timezone-aware columns."""

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        "ALTER TABLE Tickets_Master ALTER COLUMN Created_Date"
        " TYPE TIMESTAMP WITHOUT TIME ZONE USING Created_Date"
    )
    op.execute(
        "ALTER TABLE Tickets_Master ALTER COLUMN Closed_Date"
        " TYPE TIMESTAMP WITHOUT TIME ZONE USING Closed_Date"
    )
    op.execute(
        "ALTER TABLE Tickets_Master ALTER COLUMN LastModified"
        " TYPE TIMESTAMP WITHOUT TIME ZONE USING LastModified"
    )
    op.execute(
        "ALTER TABLE Ticket_Messages ALTER COLUMN DateTimeStamp"
        " TYPE TIMESTAMP WITHOUT TIME ZONE USING DateTimeStamp"
    )
    op.execute(
        "ALTER TABLE Ticket_Attachments ALTER COLUMN UploadDateTime"
        " TYPE TIMESTAMP WITHOUT TIME ZONE USING UploadDateTime"
    )
    op.execute(
        "ALTER TABLE OnCall_Shifts ALTER COLUMN start_time"
        " TYPE TIMESTAMP WITHOUT TIME ZONE USING start_time"
    )
    op.execute(
        "ALTER TABLE OnCall_Shifts ALTER COLUMN end_time"
        " TYPE TIMESTAMP WITHOUT TIME ZONE USING end_time"
    )
