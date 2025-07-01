from ai.openai_agent import suggest_ticket_response

def ai_suggest_response(ticket: dict, context: str = ""):
    return suggest_ticket_response(ticket, context)
