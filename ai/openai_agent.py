from typing import Any, Dict

import openai

from openai import APITimeoutError, OpenAIError
from config import OPENAI_API_KEY


def suggest_ticket_response(ticket: Dict[str, Any], context: str = "") -> str:
    if not OPENAI_API_KEY:

        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    prompt = (
        "You are a Tier 1 help desk agent for a truck stop. Here is the ticket:\n"
        f"{ticket}\n"
        f"Context: {context}\n"
        "Suggest the best response, including troubleshooting or assignment if possible."
    )
    try:

        response = openai.ChatCompletion.create(  # type: ignore[attr-defined]

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

