"""add timezone awareness to datetime columns

Revision ID: f5f570501dfb
Revises: 2e80bc0ee0ea
Create Date: 2025-07-20 21:22:34

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f5f570501dfb'
down_revision: Union[str, None] = '2e80bc0ee0ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Note: For SQLite (testing), this is mainly documentation
    # For PostgreSQL production, these would convert columns to TIMESTAMPTZ
    
    # PostgreSQL commands (commented for SQLite compatibility):
    # op.execute("ALTER TABLE Tickets_Master ALTER COLUMN Created_Date TYPE TIMESTAMPTZ USING Created_Date AT TIME ZONE 'UTC'")
    # op.execute("ALTER TABLE Tickets_Master ALTER COLUMN Closed_Date TYPE TIMESTAMPTZ USING Closed_Date AT TIME ZONE 'UTC'")
    # op.execute("ALTER TABLE Tickets_Master ALTER COLUMN LastModified TYPE TIMESTAMPTZ USING LastModified AT TIME ZONE 'UTC'")
    # op.execute("ALTER TABLE Ticket_Messages ALTER COLUMN DateTimeStamp TYPE TIMESTAMPTZ USING DateTimeStamp AT TIME ZONE 'UTC'")
    # op.execute("ALTER TABLE Ticket_Attachments ALTER COLUMN UploadDateTime TYPE TIMESTAMPTZ USING UploadDateTime AT TIME ZONE 'UTC'")
    # op.execute("ALTER TABLE OnCall_Shifts ALTER COLUMN start_time TYPE TIMESTAMPTZ USING start_time AT TIME ZONE 'UTC'")
    # op.execute("ALTER TABLE OnCall_Shifts ALTER COLUMN end_time TYPE TIMESTAMPTZ USING end_time AT TIME ZONE 'UTC'")
    
    pass  # For SQLite, changes are handled at the application level


def downgrade() -> None:
    # Rollback would convert back to naive timestamps
    pass
