import openai
from openai import OpenAIError, Timeout
from config import require_openai_key


def _set_api_key() -> None:
    """Configure the OpenAI client with the API key."""
    openai.api_key = require_openai_key()


def suggest_ticket_response(ticket: dict, context: str = "") -> str:
    """Return a suggested response for a help desk ticket using OpenAI."""
    _set_api_key()
    prompt = (
        "You are a Tier 1 help desk agent for a truck stop. Here is the ticket:\n"
        f"{ticket}\n"
        f"Context: {context}\n"
        "Suggest the best response, including troubleshooting or assignment if possible."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            timeout=15,
        )
        return response["choices"][0]["message"]["content"]
    except Timeout:
        return "OpenAI request timed out."
    except OpenAIError as e:
        return f"OpenAI API error: {e}"

