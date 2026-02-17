"""Conversation Summarizer Service.

G1: Summarize recent conversation history into a concise context string
for injection into RAG prompts. Uses Gemini Flash for cost-effective
summarization.

The summary enables follow-up questions to work properly:
- "What about their obligations?" → knows who "their" refers to
- "Tell me more" → knows what was previously discussed

Summaries are cached in Redis per session to avoid re-summarizing
on every message. Cache is invalidated when new messages are added.
"""

from __future__ import annotations

from functools import lru_cache

import structlog
from google.genai import types

from app.core.config import get_settings
from app.core.gemini_client import get_gemini_client
from app.models.memory import SessionMessage
from app.services.memory.redis_client import get_redis_client
from app.services.memory.redis_keys import SESSION_TTL, _validate_uuid

logger = structlog.get_logger(__name__)

# Only summarize when session has more than this many messages
MIN_MESSAGES_FOR_SUMMARY = 3

# Max messages to include in summarization (most recent)
MAX_MESSAGES_TO_SUMMARIZE = 10

# Redis cache TTL for summaries (same as session TTL)
SUMMARY_CACHE_TTL = SESSION_TTL

SUMMARIZER_SYSTEM_PROMPT = """You are a conversation context summarizer for a legal research assistant.

Given a conversation between a user (attorney) and an assistant about legal case documents,
produce a concise context summary that captures:

1. The main topic(s) being discussed (e.g., "termination clauses in the partnership agreement")
2. Key entities mentioned (names, parties, documents, dates)
3. The current line of inquiry (what the user is trying to understand)

Rules:
- Keep the summary to 2-4 sentences maximum
- Focus on what would help answer the NEXT follow-up question
- Use specific names and references, not generic descriptions
- If the user was asking about a specific party, name them
- Do NOT include greetings, pleasantries, or meta-conversation"""


def _summary_cache_key(matter_id: str, user_id: str, msg_count: int) -> str:
    """Generate Redis key for cached conversation summary.

    Includes message count so the cache auto-expires when new messages
    are added — no explicit invalidation needed.
    """
    _validate_uuid(matter_id, "matter_id")
    _validate_uuid(user_id, "user_id")
    return f"session:{matter_id}:{user_id}:conv_summary:{msg_count}"


class ConversationSummarizer:
    """Summarizes conversation history for RAG prompt injection."""

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.gemini_model
        self.client = get_gemini_client()
        self.redis = get_redis_client()

    async def get_summary(
        self,
        matter_id: str,
        user_id: str,
        messages: list[SessionMessage],
    ) -> str | None:
        """Get conversation summary, using cache if available.

        Cache key includes message count, so the cache auto-expires
        when new messages are added — no explicit invalidation needed.

        Args:
            matter_id: Matter UUID for isolation.
            user_id: User UUID.
            messages: Recent session messages.

        Returns:
            Summary string, or None if too few messages.
        """
        if len(messages) < MIN_MESSAGES_FOR_SUMMARY:
            return None

        msg_count = len(messages)

        # Check cache first (keyed by message count — new messages = new key)
        cached = await self._get_cached_summary(matter_id, user_id, msg_count)
        if cached is not None:
            return cached

        # Generate new summary
        summary = await self._summarize(messages)
        if summary:
            await self._cache_summary(matter_id, user_id, msg_count, summary)

        return summary

    async def _summarize(self, messages: list[SessionMessage]) -> str | None:
        """Generate summary from messages using Gemini Flash."""
        # Take most recent messages
        recent = messages[-MAX_MESSAGES_TO_SUMMARIZE:]

        # Format conversation for the LLM
        conversation_text = "\n".join(
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:500]}"
            for m in recent
        )

        prompt = f"Summarize the following conversation context:\n\n{conversation_text}"

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SUMMARIZER_SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=200,
                ),
            )

            summary = response.text.strip() if response.text else None

            if summary:
                logger.debug(
                    "conversation_summarized",
                    message_count=len(recent),
                    summary_length=len(summary),
                )

            return summary

        except Exception as e:
            logger.warning("conversation_summarize_failed", error=str(e))
            return None

    async def _get_cached_summary(
        self, matter_id: str, user_id: str, msg_count: int,
    ) -> str | None:
        """Retrieve cached summary from Redis."""
        try:
            key = _summary_cache_key(matter_id, user_id, msg_count)
            data = await self.redis.get(key)
            if data:
                return data if isinstance(data, str) else data.decode("utf-8")
        except Exception as e:
            logger.debug("summary_cache_get_failed", error=str(e))
        return None

    async def _cache_summary(
        self, matter_id: str, user_id: str, msg_count: int, summary: str,
    ) -> None:
        """Cache summary in Redis with session-matching TTL."""
        try:
            key = _summary_cache_key(matter_id, user_id, msg_count)
            await self.redis.set(key, summary, ex=SUMMARY_CACHE_TTL)
        except Exception as e:
            logger.debug("summary_cache_set_failed", error=str(e))


@lru_cache(maxsize=1)
def get_conversation_summarizer() -> ConversationSummarizer:
    """Get singleton ConversationSummarizer instance."""
    return ConversationSummarizer()
