from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")

@dataclass
class OperationResult(Generic[T]):
    """Generic result wrapper for tool operations."""

    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
