from src.shared.schemas.agent_data import AdvancedQuery, MAX_LIMIT


def test_limit_clamped_to_max():
    q = AdvancedQuery(limit=MAX_LIMIT + 1)
    assert q.limit == MAX_LIMIT

