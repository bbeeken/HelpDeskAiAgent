"""System-wide utilities and shared functionality."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar
from datetime import datetime
from src.shared.utils.date_format import parse_db_datetime

import httpx

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Operation result wrapper
# -------------------------------------------------------------------
T = TypeVar("T")


@dataclass
class OperationResult(Generic[T]):
    """Generic result wrapper for tool operations."""

    success: bool
    data: Optional[T] = None
    error: Optional[str] = None


def parse_search_datetime(date_str: str | None) -> datetime | None:
    """Safely parse datetime with proper error handling."""
    if not date_str:
        return None
    try:
        # First attempt database-specific format
        dt = parse_db_datetime(date_str)
    except ValueError:
        dt = None
    if dt is None:
        try:
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            raise ValueError(f"Invalid datetime format: {date_str}")
    # Normalize microseconds to milliseconds precision to match DB expectations
    if dt.microsecond % 1000:
        dt = dt.replace(microsecond=(dt.microsecond // 1000) * 1000)
    return dt


# -------------------------------------------------------------------
# Simple CLI for interacting with the API
# -------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


async def create_ticket(_args: argparse.Namespace) -> None:
    """Read JSON from STDIN and post to /ticket."""
    payload = json.load(sys.stdin)
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        try:
            resp = await client.post("/ticket", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("HTTP error creating ticket: %s", exc)
            return
        sys.stdout.write(resp.text)
        sys.stdout.flush()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HelpDesk API CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-ticket", help="Create a helpdesk ticket")
    p.set_defaults(func=create_ticket)
    return parser


def cli_main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    asyncio.run(args.func(args))


if __name__ == "__main__":
    cli_main()

__all__ = ["OperationResult", "create_ticket", "cli_main", "parse_search_datetime"]
