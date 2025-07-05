"""Helper functions for interacting with the AI backend."""

from typing import Any, AsyncGenerator, Dict, Optional, List
import logging
from datetime import datetime, timezone
from enum import Enum
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field
from fastmcp import Client

from ai.mcp_agent import (
    suggest_ticket_response as mcp_suggest_response,
    stream_ticket_response as mcp_stream_ticket_response,
)

logger = logging.getLogger(__name__)


class ResponseTone(str, Enum):
    """Response tone options for AI-generated content."""

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    EMPATHETIC = "empathetic"
    URGENT = "urgent"


class AIResponseQuality(BaseModel):
    """Quality metrics for AI-generated responses."""

    relevance_score: float = Field(ge=0, le=1)
    completeness_score: float = Field(ge=0, le=1)
    clarity_score: float = Field(ge=0, le=1)
    safety_score: float = Field(ge=0, le=1)
    overall_quality: float = Field(ge=0, le=1)
    improvement_suggestions: List[str] = []


@dataclass
class _SafetyPatterns:
    pii: List[str]
    prompt_injection: List[str]
    sensitive_actions: List[str]


class AITools:
    """Enhanced AI helper utilities."""

    def __init__(self, mcp_url: str, timeout: int = 30):
        self.mcp_url = mcp_url
        self.timeout = timeout
        self._client: Optional[Client] = None
        self._safety_patterns = self._load_safety_patterns()

    def _load_safety_patterns(self) -> _SafetyPatterns:
        return _SafetyPatterns(
            pii=[r"\b\d{3}-\d{2}-\d{4}\b", r"\b\d{16}\b"],
            prompt_injection=["ignore previous instructions", "system prompt"],
            sensitive_actions=["delete all", "drop table", "sudo rm"],
        )

    async def generate_ticket_response(
        self,
        ticket_context: Dict[str, Any],
        tone: ResponseTone = ResponseTone.PROFESSIONAL,
        max_length: int = 500,
        include_next_steps: bool = True,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        safety_check = await self._check_content_safety(ticket_context)
        if not safety_check["is_safe"]:
            return {
                "error": True,
                "error_type": "unsafe_content",
                "safety_issues": safety_check["issues"],
            }

        prompt = self._build_response_prompt(
            ticket_context, tone, max_length, include_next_steps, custom_instructions
        )

        parts: List[str] = []
        async for chunk in self._stream_ai_response(prompt):
            parts.append(chunk)
        text = "".join(parts)

        quality = await self._evaluate_response_quality(text, ticket_context)

        return {
            "success": True,
            "response": {
                "content": text,
                "tone": tone.value,
                "word_count": len(text.split()),
            },
            "quality_metrics": quality.dict(),
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model_used": "mcp_agent",
                "safety_verified": True,
            },
        }

    def _build_response_prompt(
        self,
        ticket_context: Dict[str, Any],
        tone: ResponseTone,
        max_length: int,
        include_next_steps: bool,
        custom_instructions: Optional[str],
    ) -> str:
        ticket = ticket_context.get("ticket", {})
        parts = [
            "You are an expert IT helpdesk technician.",
            f"Tone: {tone.value}",
            f"Limit: {max_length} characters",
            "",
            f"Subject: {ticket.get('subject', '')}",
            f"Description: {ticket.get('description', '')}",
        ]
        if custom_instructions:
            parts.extend(["", custom_instructions])
        if include_next_steps:
            parts.append("Include next steps if appropriate.")
        parts.append("Generate your response:")
        return "\n".join(parts)

    async def _stream_ai_response(self, prompt: str) -> AsyncGenerator[str, None]:
        if not self._client:
            self._client = Client(self.mcp_url)

        async with self._client:
            try:
                async for chunk in self._client.stream_tool(
                    "suggest_ticket_response", {"prompt": prompt}, timeout=self.timeout
                ):
                    if getattr(chunk, "data", None) is not None:
                        yield str(chunk.data)
                    elif getattr(chunk, "content", None):
                        for block in chunk.content:
                            if hasattr(block, "text"):
                                yield block.text
            except Exception:
                logger.exception("AI response streaming failed")

    async def _check_content_safety(self, content: Any) -> Dict[str, Any]:
        issues: List[str] = []
        text = str(content)
        for pattern in self._safety_patterns.pii:
            if re.search(pattern, text):
                issues.append("pii")
        lower = text.lower()
        for phrase in self._safety_patterns.prompt_injection:
            if phrase in lower:
                issues.append("prompt_injection")
        for cmd in self._safety_patterns.sensitive_actions:
            if cmd in lower:
                issues.append("dangerous_command")
        return {"is_safe": not issues, "issues": issues}

    async def _evaluate_response_quality(
        self, response: str, context: Dict[str, Any]
    ) -> AIResponseQuality:
        relevance = 0.0
        subject = context.get("ticket", {}).get("subject", "").lower()
        if subject:
            overlap = len(set(subject.split()) & set(response.lower().split()))
            relevance = min(overlap / max(len(subject.split()), 1), 1.0)
        return AIResponseQuality(
            relevance_score=relevance,
            completeness_score=1.0 if len(response.split()) > 5 else 0.5,
            clarity_score=1.0,
            safety_score=1.0,
            overall_quality=relevance * 0.5 + 0.5,
        )


async def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> str:
    """Return a suggested response using the MCP backend."""
    return await mcp_suggest_response(ticket, context)


async def ai_stream_response(
    ticket: Dict[str, Any], context: str = ""
) -> AsyncGenerator[str, None]:
    """Stream a suggested response to the ticket."""
    async for chunk in mcp_stream_ticket_response(ticket, context):
        yield chunk


# Export main classes for external use
__all__ = [
    "AITools",
    "ResponseTone",
    "AIResponseQuality",
    "ai_suggest_response",
    "ai_stream_response",
]
