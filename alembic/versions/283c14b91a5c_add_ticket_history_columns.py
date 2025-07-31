"""add ticket history columns

Revision ID: 283c14b91a5c
Revises: e1a052713de2
Create Date: 2025-08-16 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from src.core.repositories.sql import CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL

revision: str = '283c14b91a5c'
down_revision: Union[str, None] = 'e1a052713de2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CREATE_VIEW_SQL = CREATE_VTICKET_MASTER_EXPANDED_VIEW_SQL

OLD_VIEW_SQL = """
CREATE VIEW V_Ticket_Master_Expanded AS
SELECT t.Ticket_ID,
       t.Subject,
       t.Ticket_Body,
       t.Ticket_Status_ID,
       ts.Label AS Ticket_Status_Label,
       t.Ticket_Contact_Name,
       t.Ticket_Contact_Email,
       t.Asset_ID,
       a.Label AS Asset_Label,
       t.Site_ID,
       s.Label AS Site_Label,
       t.Ticket_Category_ID,
       c.Label AS Ticket_Category_Label,
       t.Version,
       t.Created_Date,
       t.Assigned_Name,
       t.Assigned_Email,
       t.Severity_ID,
       t.Assigned_Vendor_ID,
       v.Name AS Assigned_Vendor_Name,
       t.Resolution,
       p.Level AS Priority_Level
FROM Tickets_Master t
LEFT JOIN Ticket_Status ts ON ts.ID = t.Ticket_Status_ID
LEFT JOIN Assets a ON a.ID = t.Asset_ID
LEFT JOIN Sites s ON s.ID = t.Site_ID
LEFT JOIN Ticket_Categories c ON c.ID = t.Ticket_Category_ID
LEFT JOIN Vendors v ON v.ID = t.Assigned_Vendor_ID
LEFT JOIN Priority_Levels p ON p.ID = t.Severity_ID
"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
    op.add_column('Tickets_Master', sa.Column('Closed_Date', sa.DateTime(), nullable=True))
    op.add_column('Tickets_Master', sa.Column('LastModified', sa.DateTime(), nullable=True))
    op.add_column('Tickets_Master', sa.Column('LastModfiedBy', sa.String(), nullable=True))
    op.execute(CREATE_VIEW_SQL)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS V_Ticket_Master_Expanded")
    op.drop_column('Tickets_Master', 'LastModfiedBy')
    op.drop_column('Tickets_Master', 'LastModified')
    op.drop_column('Tickets_Master', 'Closed_Date')
    op.execute(OLD_VIEW_SQL)
