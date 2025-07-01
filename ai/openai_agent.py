import openai
import logging
from openai import OpenAIError, APITimeoutError
from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL_NAME,
    OPENAI_TIMEOUT,
)

logger = logging.getLogger(__name__)


def suggest_ticket_response(ticket: dict, context: str = "") -> str:
    logger.info("Requesting AI response for ticket %s", ticket.get("Ticket_ID"))
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY environment variable not set")
        raise RuntimeError("OPENAI_API_KEY environment variable not set")
    openai.api_key = OPENAI_API_KEY

    prompt = (
        "You are a Tier 1 help desk agent for a truck stop. Here is the ticket:\n"
        f"{ticket}\n"
        f"Context: {context}\n"
        "Suggest the best response, including troubleshooting or assignment if possible."
    )
    try:
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL_NAME,
            messages=[{"role": "system", "content": prompt}],
            timeout=OPENAI_TIMEOUT,
        )
        result = response["choices"][0]["message"]["content"]
        logger.info("AI response received for ticket %s", ticket.get("Ticket_ID"))
        return result
    except APITimeoutError:
        logger.exception("OpenAI request timed out")
        return "OpenAI request timed out."

    except OpenAIError as exc:
        logger.exception("OpenAI API error")
        return f"OpenAI API error: {exc}"

