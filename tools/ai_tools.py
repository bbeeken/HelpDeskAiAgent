
from typing import Any, Dict

import logging
from ai.openai_agent import suggest_ticket_response

logger = logging.getLogger(__name__)


async def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> str:

    return await suggest_ticket_response(ticket, context)

