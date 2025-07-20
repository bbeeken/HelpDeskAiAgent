import asyncio
import logging
import os
import uuid
import json
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, UTC
from typing import Any, Dict, List

import sentry_sdk
from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi_mcp import FastApiMCP
from jsonschema import Draft7Validator, ValidationError as JsonSchemaError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1 import get_db, register_routes
from config import ERROR_TRACKING_DSN
from src.core.repositories.models import Base
from src.infrastructure.database import engine
from src.shared.exceptions import DatabaseError, ErrorResponse, NotFoundError, ValidationError
from limiter import limiter
from src.mcp_server import Tool, create_enhanced_server
from src.tool_list import TOOLS

# Configure logger for this module
logger = logging.getLogger(__name__)

# Application constants
APP_VERSION = "0.1.0"
REQUEST_TIMEOUT = 30.0
MAX_REQUEST_SIZE = 10_000_000  # 10MB

# Correlation ID context variable for log records
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

# Record startup time to report uptime
START_TIME = datetime.now(UTC)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.correlation_id = _correlation_id_var.get()
        return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging and initialize application components."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(correlation_id)s - %(name)s - %(message)s",
    )
    logging.getLogger().addFilter(CorrelationIdFilter())

    # Initialize Sentry if configured
    if ERROR_TRACKING_DSN:
        sentry_sdk.init(dsn=ERROR_TRACKING_DSN)
        logger.info("Sentry error tracking enabled")

    # Set up rate limiter
    app.state.limiter = limiter

    # Record actual startup time
    global START_TIME
    START_TIME = datetime.now(UTC)

    # Initialize database
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        raise

    # Initialize MCP after all setup is complete
    app.state.mcp = FastApiMCP(app)
    app.state.mcp.mount()
    logger.info("MCP server initialized")

    yield

    # Cleanup
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning("Error during database cleanup: %s", e)


# Create FastAPI application
app = FastAPI(
    title="Truck Stop MCP Helpdesk API",
    version=APP_VERSION,
    lifespan=lifespan
)

# Add middleware (order matters!)
if os.getenv("ENABLE_RATE_LIMITING", "true").lower() not in {"0", "false", "no"}:
    app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID to each request for tracing."""
    correlation_id = (
        request.headers.get("X-Request-ID")
        or request.headers.get("X-Correlation-ID")
        or uuid.uuid4().hex
    )
    request.state.correlation_id = correlation_id
    token = _correlation_id_var.set(correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        _correlation_id_var.reset(token)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size to prevent memory issues."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(
            status_code=413,
            content={
                "error": "Request too large",
                "message": f"Request size exceeds {MAX_REQUEST_SIZE} bytes limit"
            },
        )
    return await call_next(request)


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Add request timeout to prevent hanging requests."""
    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("Request timeout for %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=504,
            content={
                "error": "Request timeout",
                "message": f"Request took longer than {REQUEST_TIMEOUT} seconds"
            },
        )


# Custom OpenAPI schema
def custom_openapi() -> Dict[str, Any]:
    """Return OpenAPI schema with array parameters expanded."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version=APP_VERSION, routes=app.routes)

    # Fix array parameter schemas
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
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


# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def handle_rate_limit(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )


@app.exception_handler(NotFoundError)
async def handle_not_found(request: Request, exc: NotFoundError):
    """Handle custom not found errors."""
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(status_code=404, content=jsonable_encoder(resp))


@app.exception_handler(ValidationError)
async def handle_validation(request: Request, exc: ValidationError):
    """Handle custom validation errors."""
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(status_code=400, content=jsonable_encoder(resp))


@app.exception_handler(DatabaseError)
async def handle_database(request: Request, exc: DatabaseError):
    """Handle custom database errors."""
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
    logger.exception(
        "Unhandled exception during request to %s %s",
        request.method,
        request.url.path,
    )
    resp = ErrorResponse(
        error_code="UNEXPECTED_ERROR",
        message=str(exc) or "Internal server error",
        details=None,
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(status_code=500, content=jsonable_encoder(resp))


# MCP Tools Integration
def build_mcp_endpoint(tool: Tool, schema: Dict[str, Any]):
    """Build a FastAPI endpoint from an MCP tool."""
    validator = Draft7Validator(schema)


    async def endpoint(request: Request):
        try:
            data = await request.json()
        except Exception as e:
            return JSONResponse(
                status_code=422,
                content={"detail": f"Invalid JSON: {str(e)}"}
            )

        # Validate allowed parameters
        allowed = set(schema.get("properties", {}).keys())
        extra = set(data) - allowed
        if extra:
            return JSONResponse(
                status_code=422,
                content={"detail": f"Unexpected parameters: {', '.join(extra)}"}
            )

        # Validate schema
        try:
            validator.validate(data)
        except JsonSchemaError as exc:
            return JSONResponse(
                status_code=422,
                content={"detail": f"Schema validation error: {exc.message}"}
            )

        # Filter to only allowed parameters
        filtered = {k: data[k] for k in allowed if k in data}

        try:
            return await tool._implementation(**filtered)
        except Exception as e:
            logger.exception("Error executing tool %s", tool.name)
            return JSONResponse(
                status_code=500,
                content={"detail": f"Tool execution error: {str(e)}"}
            )

    return endpoint


# Register MCP tools as HTTP endpoints
server = create_enhanced_server()
logger.info("Enhanced MCP server active with %d tools", len(TOOLS))

for tool in TOOLS:
    schema = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
    endpoint_func = build_mcp_endpoint(tool, schema)

    app.post(
        f"/{tool.name}",
        operation_id=tool.name,
        summary=tool.description,
        openapi_extra={
            "requestBody": {
                "content": {"application/json": {"schema": schema}},
                "required": True
            }
        },
        tags=["mcp-tools"]
    )(endpoint_func)

logger.info("Registered %d MCP tools as HTTP endpoints", len(TOOLS))


# Standard API routes
register_routes(app)


# API endpoints
@app.get("/tools", tags=["mcp"])
async def list_tools() -> Dict[str, List[Dict[str, Any]]]:
    """Return a dictionary of available MCP tools."""
    return {"tools": [t.to_dict() for t in TOOLS]}


@app.get("/health", tags=["system"])
async def health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Enhanced health check with dependency testing."""
    health_status: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": APP_VERSION,
        "uptime": (datetime.now(UTC) - START_TIME).total_seconds(),
        "checks": {},
    }

    # Database health check
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=5.0)
        health_status["checks"]["database"] = {"status": "healthy"}
    except asyncio.TimeoutError:
        health_status["checks"]["database"] = {"status": "timeout"}
        health_status["status"] = "degraded"
        logger.warning("Database health check timed out")
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
        logger.error("Database health check failed: %s", e)

    return health_status


@app.get("/health/mcp", tags=["system"])
async def health_mcp() -> Dict[str, Any]:
    """Return health information about the MCP server."""
    return {
        "status": "healthy",
        "enhanced": getattr(server, "is_enhanced", False),
        "tool_count": len(TOOLS),
        "tools": [tool.name for tool in TOOLS]
    }


@app.get("/", tags=["system"])
async def root() -> Dict[str, Any]:
    """API root endpoint with basic information."""
    return {
        "name": app.title,
        "version": APP_VERSION,
        "status": "running",
        "docs_url": "/docs",
        "health_url": "/health"
    }
