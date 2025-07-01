import openai
from openai import OpenAIError, APITimeoutError
from config import OPENAI_API_KEY

# Initialize a client at import time if an API key is available.  This avoids
# repeatedly setting the key for each request.
openai_client = openai.Client(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def suggest_ticket_response(ticket: dict, context: str = "") -> str:
    """Return an AI generated response for a help desk ticket."""
    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    prompt = (
        "You are a Tier 1 help desk agent for a truck stop. Here is the ticket:\n"
        f"{ticket}\n"
        f"Context: {context}\n"
        "Suggest the best response, including troubleshooting or assignment if possible."
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            timeout=15,
        )
        return response.choices[0].message.content
    except APITimeoutError:
        return "OpenAI request timed out."

    except OpenAIError as exc:
        return f"OpenAI API error: {exc}"
