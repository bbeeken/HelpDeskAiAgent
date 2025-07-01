import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def suggest_ticket_response(ticket: dict, context: str = "") -> str:
    prompt = (
        f"You are a Tier 1 help desk agent for a truck stop. Here is the ticket:\n"
        f"{ticket}\n"
        f"Context: {context}\n"
        "Suggest the best response, including troubleshooting or assignment if possible."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}]
    )
    return response['choices'][0]['message']['content']
