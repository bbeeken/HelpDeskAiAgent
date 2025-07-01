import logging
from ai.openai_agent import suggest_ticket_response

logger = logging.getLogger(__name__)


def ai_suggest_response(ticket: dict, context: str = ""):
    logger.info("AI suggest response called for ticket %s", ticket.get("Ticket_ID"))
    return suggest_ticket_response(ticket, context)

