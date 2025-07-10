import pytest
from asgi_lifespan import LifespanManager
from main import app

@pytest.mark.asyncio
async def test_operation_ids_length():
    async with LifespanManager(app):
        schema = app.openapi()
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                operation_id = operation.get("operationId")
                assert operation_id is None or len(operation_id) <= 50
