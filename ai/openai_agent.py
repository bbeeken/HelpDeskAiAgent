from typing import Any, Dict

import logging
import openai

from openai import APITimeoutError, OpenAIError, OpenAI
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

openai_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return a singleton OpenAI client, instantiating it if necessary."""
    global openai_client
    if openai_client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY environment variable not set")
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return openai_client


def suggest_ticket_response(ticket: Dict[str, Any], context: str = "") -> str:
    client = _get_client()

    prompt = (
        "You are a Tier 1 help desk agent for a truck stop. Here is the ticket:\n"
        f"{ticket}\n"
        f"Context: {context}\n"
        "Suggest the best response, including troubleshooting or assignment if possible."
    )
    try:

        response = client.chat.completions.create(

            model="gpt-4o",

            messages=[{"role": "system", "content": prompt}],
            timeout=OPENAI_TIMEOUT,
        )

        return response.choices[0].message.content

    except APITimeoutError:
        logger.exception("OpenAI request timed out")
        return "OpenAI request timed out."

    except OpenAIError as exc:
        logger.exception("OpenAI API error")
        return f"OpenAI API error: {exc}"

