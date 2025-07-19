from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
import jsonschema
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from fastapi_mcp import FastApiMCP



from src.mcp_server import Tool, create_enhanced_server


from src.tool_list import TOOLS
from api.routes import register_routes, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os

from limiter import limiter
from errors import ErrorResponse, NotFoundError, ValidationError, DatabaseError
from db.models import Base
from db.mssql import engine
from config import ERROR_TRACKING_DSN
import sentry_sdk
from jsonschema import Draft7Validator, ValidationError as JsonSchemaError

from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, UTC
import logging
import uuid
import asyncio
from typing import List, Dict, Any

# Configure root logger so messages are output when running with uvicorn
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Correlation ID context variable for log records
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.correlation_id = _correlation_id_var.get()
        return True

# Application version
APP_VERSION = "0.1.0"

# Record startup time to report uptime
START_TIME = datetime.now(UTC)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging and initialize application components."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(correlation_id)s - %(name)s - %(message)s",
    )
    logging.getLogger().addFilter(CorrelationIdFilter())

    if ERROR_TRACKING_DSN:
        sentry_sdk.init(dsn=ERROR_TRACKING_DSN)
        logger.info("Sentry error tracking enabled")

    app.state.limiter = limiter

    global START_TIME
    START_TIME = datetime.now(UTC)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

app = FastAPI(title="Truck Stop MCP Helpdesk API", lifespan=lifespan)
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}),
)
if os.getenv("ENABLE_RATE_LIMITING", "true").lower() not in {"0", "false", "no"}:
    app.add_middleware(SlowAPIMiddleware)

register_routes(app)

def custom_openapi() -> Dict[str, Any]:
    """Return OpenAPI schema with array parameters expanded."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=APP_VERSION, routes=app.routes)
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            for param in operation.get("parameters", []):
                s = param.get("schema", {})
                if "anyOf" in s and not s.get("items"):
                    array_schema = next((a for a in s["anyOf"] if a.get("type") == "array"), None)
                    if array_schema and array_schema.get("items"):
                        param["schema"] = {
                            "type": "array",
                            "items": array_schema["items"],
                            "title": s.get("title", param["name"]),
                        }
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi

# --- Dynamically expose MCP tools as HTTP endpoints ---
server = create_enhanced_server()
logger.info(
    "Enhanced MCP server active with %d tools", len(getattr(server, "_tools", []))
)


def build_endpoint(tool: Tool, schema: Dict[str, Any]):
    validator = Draft7Validator(schema)

    async def endpoint(request: Request):
        data = await request.json()
        allowed = set(schema.get("properties", {}).keys())
        extra = set(data) - allowed
        if extra:
            return JSONResponse(status_code=422, content={"detail": "Unexpected parameters"})
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.exceptions.ValidationError as exc:
            return JSONResponse(status_code=422, content={"detail": exc.message})
        filtered = {k: data[k] for k in allowed if k in data}

        try:
            validator.validate(filtered)
        except JsonSchemaError as exc:
            return JSONResponse(status_code=422, content={"detail": str(exc.message)})

        return await tool._implementation(**filtered)

    return endpoint

for tool in TOOLS:
    schema = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
    app.post(
        f"/{tool.name}",
        operation_id=tool.name,
        summary=tool.description,
        openapi_extra={
            "requestBody": {
                "content": {"application/json": {"schema": schema}}
            }
        },
    )(build_endpoint(tool, schema))

@app.get("/tools")
async def list_tools() -> Dict[str, List[Dict[str, Any]]]:


  
    """Return a dictionary of available tools."""

    

    return {"tools": [t.to_dict() for t in TOOLS]}

app.state.mcp = FastApiMCP(app)
app.state.mcp.mount()


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Add request timeout to prevent hanging requests."""
    try:
        return await asyncio.wait_for(call_next(request), timeout=30.0)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": "Request timeout", "message": "Request took too long"},
        )


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size to prevent memory issues."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10_000_000:
        return JSONResponse(
            status_code=413,
            content={"error": "Request too large"},
        )
    return await call_next(request)

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    token = _correlation_id_var.set(correlation_id)
    try:
        response = await call_next(request)
    finally:
        _correlation_id_var.reset(token)
    response.headers["X-Request-ID"] = correlation_id
    return response

@app.exception_handler(NotFoundError)
async def handle_not_found(request: Request, exc: NotFoundError):
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(status_code=404, content=jsonable_encoder(resp))

@app.exception_handler(ValidationError)
async def handle_validation(request: Request, exc: ValidationError):
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(status_code=400, content=jsonable_encoder(resp))

@app.exception_handler(DatabaseError)
async def handle_database(request: Request, exc: DatabaseError):
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(status_code=500, content=jsonable_encoder(resp))

@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    """Convert unexpected errors to JSON with traceback logging."""
    logger.exception("Unhandled exception during request")
    resp = ErrorResponse(
        error_code="UNEXPECTED_ERROR",
        message=str(exc) or "Internal server error",
        details=None,
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(status_code=500, content=jsonable_encoder(resp))

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Enhanced health check with dependency testing."""
    health_status: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": APP_VERSION,
        "uptime": (datetime.now(UTC) - START_TIME).total_seconds(),
        "checks": {},
    }

    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=5.0)
        health_status["checks"]["database"] = {"status": "healthy"}
    except asyncio.TimeoutError:
        health_status["checks"]["database"] = {"status": "timeout"}
        health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"

    return health_status


@app.get("/health/mcp")
async def health_mcp() -> Dict[str, Any]:
    """Return health information about the MCP server."""
    return {
        "enhanced": getattr(server, "is_enhanced", False),
        "tool_count": len(TOOLS),
    }
