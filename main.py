from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi_mcp import FastApiMCP



from src.enhanced_mcp_server import create_server, Tool
from src.mcp_server import create_enhanced_server


from src.tool_list import TOOLS
from api.routes import register_routes, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from limiter import limiter
from errors import ErrorResponse, NotFoundError, ValidationError, DatabaseError
from db.models import Base
from db.mssql import engine

from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, UTC
import logging
import uuid
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
app.add_middleware(SlowAPIMiddleware)

register_routes(app)

# --- Dynamically expose MCP tools as HTTP endpoints ---
server = create_enhanced_server()
if getattr(server, "is_enhanced", False):
    logger.info("Enhanced MCP server active with %d tools", len(getattr(server, "_tools", [])))
else:
    logger.info("Basic MCP server active")

def build_endpoint(tool: Tool, schema: Dict[str, Any]):
    async def endpoint(request: Request):
        data = await request.json()
        allowed = set(schema.get("properties", {}).keys())
        extra = set(data) - allowed
        if extra:
            return JSONResponse(status_code=422, content={"detail": "Unexpected parameters"})
        filtered = {k: data[k] for k in allowed if k in data}
        return await tool._implementation(**filtered)

    return endpoint

for tool in TOOLS:
    schema = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
    app.post(f"/{tool.name}", operation_id=tool.name)(build_endpoint(tool, schema))

@app.get("/tools")
async def list_tools() -> Dict[str, List[Dict[str, Any]]]:
    """Return a dictionary of available tools."""
    return {"tools": [t.to_dict() for t in TOOLS]}

app.state.mcp = FastApiMCP(app)
app.state.mcp.mount()

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
    """Return basic service health information."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    uptime = (datetime.now(UTC) - START_TIME).total_seconds()
    return {"db": db_status, "uptime": uptime, "version": APP_VERSION}


@app.get("/health/mcp")
async def health_mcp() -> Dict[str, Any]:
    """Return health information about the MCP server."""
    return {
        "enhanced": getattr(server, "is_enhanced", False),
        "tool_count": len(TOOLS),
    }
