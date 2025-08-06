from src.core.repositories.models import Ticket


def test_ticket_columns_are_unique():
    column_names = [col.name for col in Ticket.__table__.columns]
    duplicates = {name for name in column_names if column_names.count(name) > 1}
    assert len(column_names) == len(set(column_names)), f"Duplicate columns found: {duplicates}"
