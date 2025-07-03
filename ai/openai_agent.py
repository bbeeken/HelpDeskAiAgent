from typing import Any, Dict

import logging
import openai

from openai import APITimeoutError, OpenAIError
from config import OPENAI_API_KEY, OPENAI_MODEL_NAME, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)

# Lazily created OpenAI client instance
openai_client: openai.AsyncClient | None = None


def set_client(client: openai.AsyncClient | None) -> None:
    """Override the cached OpenAI client used by this module."""
    global openai_client
    openai_client = client


def _get_client() -> openai.AsyncClient:
    """Return a reusable OpenAI client instance."""
    global openai_client

    if openai_client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY environment variable not set")

        openai_client = openai.AsyncClient(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT)

    return openai_client


async def suggest_ticket_response(ticket: Dict[str, Any], context: str = "") -> str:
    """Generate a suggested response to a ticket using OpenAI."""

    client = _get_client()

    prompt = (
        "You are a Tier 1 help desk agent for a truck stop. Here is the ticket:\n"
        f"{ticket}\n"
        f"Context: {context}\n"
        "Suggest the best response, including troubleshooting or assignment if possible."
    )

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=[{"role": "system", "content": prompt}],
        )
        content = response.choices[0].message.content
        return content or ""

    except APITimeoutError:
        logger.exception("OpenAI request timed out")
        return "OpenAI request timed out."

    except OpenAIError as exc:
        logger.exception("OpenAI API error")
        return f"OpenAI API error: {exc}"
