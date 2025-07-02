
from fastapi import FastAPI, Request

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import text
from db.mssql import SessionLocal
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.routes import router
from limiter import limiter

from datetime import datetime
from errors import ErrorResponse, NotFoundError, ValidationError, DatabaseError

VERSION = "0.1.0"
start_time = datetime.utcnow()


app = FastAPI(title="Truck Stop MCP Helpdesk API")
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}),
)
app.add_middleware(SlowAPIMiddleware)
app.include_router(router)



@app.exception_handler(NotFoundError)
async def handle_not_found(request: Request, exc: NotFoundError):
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=404, content=jsonable_encoder(resp))


@app.exception_handler(ValidationError)
async def handle_validation(request: Request, exc: ValidationError):
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=400, content=jsonable_encoder(resp))


@app.exception_handler(DatabaseError)
async def handle_database(request: Request, exc: DatabaseError):
    resp = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=500, content=jsonable_encoder(resp))


@app.get("/health")
async def health() -> dict:
    """Simple health check endpoint."""
    db_status = "ok"
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    uptime = (datetime.utcnow() - start_time).total_seconds()
    return {"db": db_status, "uptime": uptime, "version": VERSION}

