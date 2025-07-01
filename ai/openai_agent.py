import openai
from openai import OpenAIError, APITimeoutError
from config import OPENAI_API_KEY

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable not set")

openai.api_key = OPENAI_API_KEY


def suggest_ticket_response(ticket: dict, context: str = "") -> str:
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
    except APITimeoutError:
        return "OpenAI request timed out."
    except OpenAIError as exc:
        return f"OpenAI API error: {exc}"
