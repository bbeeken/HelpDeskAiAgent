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


@pytest.mark.asyncio
async def test_tool_request_body_present():
    async with LifespanManager(app):
        schema = app.openapi()
        g_ticket_post = schema["paths"]["/get_ticket"]["post"]
        assert "requestBody" in g_ticket_post
        content = g_ticket_post["requestBody"]["content"]
        assert "application/json" in content
        props = content["application/json"]["schema"]["properties"]
        assert "include_full_context" in props
        assert props["include_full_context"]["type"] == "boolean"
