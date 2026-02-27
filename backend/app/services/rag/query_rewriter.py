"""Query Rewriter Service.

Rewrites user queries using conversation context to produce standalone queries
that can be understood without conversation history. This replaces the previous
approach of injecting conversation summaries into generation prompts (G2).

Industry best practice (LangChain, Google Research, MIT mtRAG):
- Use conversation history for query rewriting BEFORE retrieval
- Keep generation prompts clean — only system prompt + chunks + query
- Rewritten queries improve retrieval quality without hallucination risk

Uses Gemini Flash for cost-effective rewriting (same as summarizer).
"""

from __future__ import annotations

from functools import lru_cache

import structlog
from google.genai import types

from app.core.config import get_settings
from app.core.cost_tracking import (
    CostTracker,
    LLMProvider,
    estimate_tokens,
    persist_cost,
)
from app.core.gemini_client import get_gemini_client
from app.core.llm_rate_limiter import LLMProvider as RateLimitProvider, get_rate_limiter
from app.core.prompt_boundaries import _escape_xml_tags

logger = structlog.get_logger(__name__)

# Skip rewriting for sessions with fewer messages (query is already standalone)
MIN_MESSAGES_FOR_REWRITE = 3

REWRITER_SYSTEM_PROMPT = """You are a query rewriter for a legal research assistant.

Given the conversation context and the user's latest question,
rewrite the question as a standalone query that can be understood without conversation history.

Rules:
- If the question is already standalone, return it unchanged
- ALWAYS resolve pronouns (he/she/they/it/them/this) to specific entity names from context
- Carry forward the specific topic if the question is a follow-up
- If the question is on a completely different topic, return it as-is (ignore history)
- The rewritten query must be a complete, grammatical sentence
- Preserve legal terminology exactly as stated
- Output ONLY the rewritten query, nothing else — no explanation, no quotes

Examples:

Context: User asked about disputed shares. Assistant explained Nirav Jobalia denied the applicant's claims about benami shares.
Entities: Nirav D. Jobalia, Jyoti H. Mehta, Custodian
Question: What did he claim about the property?
Rewritten: What did Nirav D. Jobalia claim about the property?

Context: User asked about termination clauses in the partnership agreement between ABC Corp and XYZ Ltd.
Entities: ABC Corp, XYZ Ltd
Question: What about penalties?
Rewritten: What penalties are specified for termination in the partnership agreement between ABC Corp and XYZ Ltd?

Context: User asked about the filing date of the Custodian's affidavit, which was filed on March 26, 2024.
Entities: Custodian, Jyoti H. Mehta
Question: Tell me more
Rewritten: Tell me more about the Custodian's affidavit filed on March 26, 2024

Context: User discussed share ownership disputes involving Harshad Mehta and the Jobalia family.
Entities: Harshad S. Mehta, Nirav D. Jobalia
Question: What is the definition of negligence under Indian law?
Rewritten: What is the definition of negligence under Indian law?"""


def _is_degraded_rewrite(original: str, rewritten: str) -> bool:
    """Check if the rewrite is truncated or worse than the original.

    Returns True if we should fall back to the original query.
    """
    orig_words = original.lower().split()
    rewritten_words = rewritten.lower().split()

    # Rewrite is suspiciously shorter (lost content)
    if len(rewritten_words) < len(orig_words) - 1 and len(orig_words) > 3:
        return True

    # Rewrite ends mid-sentence (no terminal punctuation and original had it)
    orig_has_punct = original.rstrip()[-1:] in ".?!"
    rewritten_has_punct = rewritten.rstrip()[-1:] in ".?!"
    if orig_has_punct and not rewritten_has_punct:
        return True

    return False


async def rewrite_query(
    query: str,
    conversation_summary: str | None,
    entities: list[str] | None = None,
    matter_id: str | None = None,
) -> str:
    """Rewrite a query using conversation context to make it standalone.

    Args:
        query: The user's raw query.
        conversation_summary: Summary of recent conversation (from G1 summarizer).
        entities: List of entity names mentioned in the session.
        matter_id: Optional matter ID for cost tracking.

    Returns:
        Rewritten standalone query, or original query if rewriting
        is skipped or fails.
    """
    # No context to rewrite with — return as-is
    if not conversation_summary:
        return query

    # SECURITY: Escape XML tags in query to prevent prompt injection (C1)
    safe_query = _escape_xml_tags(query)

    # Build the rewriter prompt
    entity_str = ", ".join(entities) if entities else "none identified"
    prompt = (
        f"Conversation context:\n{conversation_summary}\n\n"
        f"Key entities: {entity_str}\n\n"
        f"User's latest question: {safe_query}\n\n"
        f"Rewritten standalone query:"
    )

    try:
        settings = get_settings()
        client = get_gemini_client()

        gemini_limiter = get_rate_limiter(RateLimitProvider.GEMINI)
        async with gemini_limiter:
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=REWRITER_SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=256,
                ),
            )

        rewritten = response.text.strip() if response.text else None

        if not rewritten:
            logger.debug("query_rewrite_empty_response", query=query[:100])
            return query

        # Strip wrapping quotes the model sometimes adds
        if (rewritten.startswith('"') and rewritten.endswith('"')) or (
            rewritten.startswith("'") and rewritten.endswith("'")
        ):
            rewritten = rewritten[1:-1].strip()

        # Validate: reject truncated/degraded rewrites — fall back to original
        if _is_degraded_rewrite(query, rewritten):
            logger.debug(
                "query_rewrite_degraded_fallback",
                original=query[:100],
                rewritten=rewritten[:100],
            )
            return query

        # Track costs
        cost_tracker = CostTracker(
            provider=LLMProvider.GEMINI_FLASH,
            operation="query_rewrite",
            matter_id=matter_id,
        )
        cost_tracker.add_tokens(
            input_tokens=estimate_tokens(prompt),
            output_tokens=estimate_tokens(rewritten),
        )
        cost_tracker.log_cost()
        await persist_cost(cost_tracker)

        logger.info(
            "query_rewritten",
            original=query[:100],
            rewritten=rewritten[:100],
            matter_id=matter_id,
        )

        return rewritten

    except Exception as e:
        logger.warning(
            "query_rewrite_failed",
            query=query[:100],
            error=str(e),
        )
        # Graceful degradation — use original query
        return query
