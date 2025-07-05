import logging
import re
from enum import Enum
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError
from fastmcp import Client

from schemas.ticket import TicketOut
from ai.mcp_agent import (
    suggest_ticket_response as mcp_suggest_response,
    stream_ticket_response as mcp_stream_ticket_response,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ResponseTone(str, Enum):
    """Available tones for AI-generated ticket responses."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    EMPATHETIC = "empathetic"
    URGENT = "urgent"


class AIResponseQuality(BaseModel):
    """Quality metrics for AI-generated responses."""
    relevance_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    clarity_score: float = Field(ge=0.0, le=1.0)
    safety_score: float = Field(ge=0.0, le=1.0)
    overall_quality: float = Field(ge=0.0, le=1.0)
    improvement_suggestions: List[str] = []


class _SafetyPatterns(BaseModel):
    """Regex patterns for simple safety filtering."""
    pii: List[str]
    prompt_injection: List[str]
    sensitive_actions: List[str]


class AITools:
    """Encapsulates MCP AI interactions with safety, quality, and tone controls."""

    def __init__(self, mcp_url: str, timeout: int = 30) -> None:
        self.mcp_url = mcp_url
        self.timeout = timeout
        self._client: Optional[Client] = None
        self._safety = _SafetyPatterns(
            pii=[r"\b\d{3}-\d{2}-\d{4}\b", r"\b\d{16}\b"],
            prompt_injection=["ignore previous instructions", "system prompt"],
            sensitive_actions=["delete all", "drop table", "sudo rm"]
        )

    def _ensure_client(self) -> Client:
        if not self._client:
            self._client = Client(self.mcp_url)
        return self._client

    def _check_safety(self, text: str) -> List[str]:
        issues: List[str] = []
        for pat in self._safety.pii:
            if re.search(pat, text):
                issues.append("pii_detected")
        lower = text.lower()
        for phrase in self._safety.prompt_injection:
            if phrase in lower:
                issues.append("prompt_injection")
        for cmd in self._safety.sensitive_actions:
            if cmd in lower:
                issues.append("dangerous_command")
        return issues

    def _evaluate_quality(self, response: str, subject: str) -> AIResponseQuality:
        subj_tokens = set(subject.lower().split())
        resp_tokens = set(response.lower().split())
        overlap = len(subj_tokens & resp_tokens)
        relevance = min(overlap / max(len(subj_tokens), 1), 1.0)
        completeness = 1.0 if len(response.split()) > 10 else 0.5
        return AIResponseQuality(
            relevance_score=relevance,
            completeness_score=completeness,
            clarity_score=1.0,
            safety_score=1.0,
            overall_quality=0.5 + 0.5 * relevance,
            improvement_suggestions=[]
        )

    def _build_prompt(
        self,
        ticket: TicketOut,
        tone: ResponseTone,
        max_tokens: int,
        include_next_steps: bool,
        extra_instructions: Optional[str]
    ) -> str:
        parts = [
            "You are an expert IT helpdesk technician.",
            f"Tone: {tone.value}",
            f"Max tokens: {max_tokens}",
            "",  # newline
            f"Subject: {ticket.subject}",
            f"Description: {ticket.ticket_body}",
        ]
        if extra_instructions:
            parts.extend(["", extra_instructions])
        if include_next_steps:
            parts.append("Include next steps if appropriate.")
        parts.append("Generate your response now:")
        return "\n".join(parts)

    async def suggest(
        self,
        raw_ticket: Dict[str, Any],
        tone: ResponseTone = ResponseTone.PROFESSIONAL,
        max_tokens: int = 500,
        include_next_steps: bool = True,
        extra_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            ticket = TicketOut.model_validate(raw_ticket)
        except ValidationError as e:
            logger.error("Invalid ticket payload: %s", e)
            raise

        prompt = self._build_prompt(
            ticket, tone, max_tokens, include_next_steps, extra_instructions
        )
        issues = self._check_safety(prompt)
        if issues:
            return {"error": "unsafe_content", "safety_issues": issues}

        client = self._ensure_client()
        async with client:
            try:
                text = await mcp_suggest_response(ticket.model_dump(), prompt)
            except Exception:
                logger.exception("MCP suggest failed")
                text = ""

        quality = self._evaluate_quality(text, ticket.subject)
        return {
            "content": text,
            "tone": tone.value,
            "quality": quality.dict(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_used": "mcp_agent",
            "safety_issues": issues
        }

    async def stream(
        self,
        raw_ticket: Dict[str, Any],
        tone: ResponseTone = ResponseTone.PROFESSIONAL,
        max_tokens: int = 500,
        include_next_steps: bool = True,
        extra_instructions: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            ticket = TicketOut.model_validate(raw_ticket)
        except ValidationError:
            logger.error("Invalid ticket payload for streaming.")
            return

        prompt = self._build_prompt(
            ticket, tone, max_tokens, include_next_steps, extra_instructions
        )
        issues = self._check_safety(prompt)
        if issues:
            yield {"error": "unsafe_content", "safety_issues": issues}
            return

        client = self._ensure_client()
        async with client:
            try:
                async for chunk in mcp_stream_ticket_response(
                    ticket.model_dump(), prompt
                ):
                    yield {"content": chunk}
            except Exception:
                logger.exception("MCP stream failed")


def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> Any:
    """Legacy helper: return suggested response text only."""
    return mcp_suggest_response(ticket, context)


async def ai_stream_response(ticket: Dict[str, Any], context: str = "") -> AsyncGenerator[str, None]:
    """Legacy helper: stream response chunks as plain strings."""
    async for chunk in mcp_stream_ticket_response(ticket, context):
        yield chunk


__all__ = [
    "AITools", "ResponseTone", "AIResponseQuality",
    "ai_suggest_response", "ai_stream_response"
]
