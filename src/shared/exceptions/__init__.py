from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[str] = None
    timestamp: datetime


class AppError(Exception):
    """Base class for application errors."""

    error_code: str = "APP_ERROR"

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    error_code = "NOT_FOUND"


class ValidationError(AppError):
    error_code = "VALIDATION_ERROR"


class DatabaseError(AppError):
    error_code = "DB_ERROR"
