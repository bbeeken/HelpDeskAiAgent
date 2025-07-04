"""Simple command-line interface for the HelpDesk API."""

import argparse
import asyncio
import json
import os
import sys

import httpx
from httpx_sse import EventSource
import logging

logger = logging.getLogger(__name__)


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


async def stream_response(_args: argparse.Namespace) -> None:
    """Read a ticket from STDIN and stream the AI response to STDOUT."""
    ticket = json.load(sys.stdin)

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        try:
            async with client.stream(
                "POST", "/ai/suggest_response/stream", json=ticket
            ) as resp:
                resp.raise_for_status()

                async for event in EventSource(resp).aiter_sse():
                    try:
                        data = json.loads(event.data)
                    except json.JSONDecodeError:
                        data = {"content": event.data}

                    sys.stdout.write(data.get("content", ""))
                    sys.stdout.flush()
        except httpx.HTTPError as exc:
            logger.exception("HTTP error in stream_response: %s", exc)
            return



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

    p = sub.add_parser("stream-response", help="Stream AI ticket response")
    p.set_defaults(func=stream_response)

    p = sub.add_parser("create-ticket", help="Create a helpdesk ticket")
    p.set_defaults(func=create_ticket)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
