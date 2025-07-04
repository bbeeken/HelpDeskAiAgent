

from fastapi import FastAPI, Request, Depends, Response
from fastapi_mcp import FastApiMCP


import logging


# Configure root logger so messages are output when running with uvicorn
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager
from contextvars import ContextVar


from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from sqlalchemy import text

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.routes import router, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from limiter import limiter

from datetime import datetime, UTC
import uuid
import asyncio
import json
import typing


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
from errors import ErrorResponse, NotFoundError, ValidationError, DatabaseError
from db.models import Base
from db.mssql import engine


app = FastAPI(title="Truck Stop MCP Helpdesk API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging and initialize application components."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(correlation_id)s - %(name)s - %(message)s",
    )
    logging.getLogger().addFilter(CorrelationIdFilter())

    app.state.limiter = limiter
    app.state.mcp = FastApiMCP(app)
    app.state.mcp.mount()

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
app.include_router(router)


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


# --- Minimal MCP SSE endpoint used for testing ---
_mcp_sessions: dict[str, asyncio.Queue] = {}


@app.get("/mcp")
async def mcp_stream() -> StreamingResponse:
    """Establish a Server-Sent Events stream for MCP messages."""
    session_id = uuid.uuid4().hex
    post_url = f"/mcp/{session_id}"
    queue: asyncio.Queue = asyncio.Queue()
    _mcp_sessions[session_id] = queue

    async def _generate() -> typing.AsyncGenerator[str, None]:
        yield f"event: endpoint\ndata: {post_url}\n\n"
        try:
            while True:
                data = await queue.get()
                yield f"event: message\ndata: {json.dumps(data)}\n\n"
        finally:
            _mcp_sessions.pop(session_id, None)

    return StreamingResponse(_generate(), media_type="text/event-stream")


@app.post("/mcp/{session_id}")
async def mcp_post(session_id: str, request: Request) -> Response:
    queue = _mcp_sessions.get(session_id)
    if not queue:
        return Response(status_code=404)
    payload = await request.json()
    await queue.put(payload)
    return Response(status_code=202)
