from typing import Any, Dict

from ai.openai_agent import suggest_ticket_response


def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> str:
    return suggest_ticket_response(ticket, context)
