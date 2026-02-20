"""Query Profile for adaptive RAG retrieval parameters.

Provides query-type-aware configuration for the RAG pipeline.
Different query types (lookup, summary, comparison) use different
retrieval parameters for optimal answer quality.

The QueryProfile is derived from intent classification and query text,
then passed through the pipeline to control:
- Number of chunks retrieved from hybrid search
- Cohere rerank top-N
- Context window size for LLM
- Answer length limits
- System prompt selection
"""

from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class QueryType(str, Enum):
    """Sub-classification of RAG queries for parameter tuning.

    Values:
        LOOKUP: Simple factoid queries (who/what/when)
        SUMMARY: Multi-document synthesis queries
        COMPARISON: Cross-document comparison queries
        TIMELINE: Chronological queries
        CITATION: Legal reference queries
        GENERAL: Default fallback
    """

    LOOKUP = "lookup"
    SUMMARY = "summary"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    CITATION = "citation"
    GENERAL = "general"


# Keywords used to detect summary sub-intent from query text
_SUMMARY_KEYWORDS = frozenset([
    "summarize", "summary", "key findings", "overview", "gist",
    "main points", "highlights", "brief", "recap", "outline",
])

# Keywords used to detect comparison sub-intent from query text
_COMPARISON_KEYWORDS = frozenset([
    "compare", "comparison", "contrast", "versus", "vs",
    "differ", "difference", "differences",
])


@dataclass(frozen=True)
class QueryProfile:
    """Retrieval parameters tuned per query type.

    Frozen dataclass — created once per query, passed through pipeline.

    Attributes:
        query_type: Classified query type
        hybrid_limit: Candidates to retrieve from hybrid search
        rerank_top_n: Top-N to keep after Cohere reranking
        max_context_chunks: Chunks sent to LLM context
        max_chunk_content: Max characters per chunk
        max_answer_length: Max answer characters (0 = no limit)
        system_prompt_key: Key to select prompt template from SYSTEM_PROMPTS
    """

    query_type: QueryType
    hybrid_limit: int
    rerank_top_n: int
    max_context_chunks: int
    max_chunk_content: int
    max_answer_length: int
    system_prompt_key: str

    @classmethod
    def default(cls) -> "QueryProfile":
        """Current behavior — backward compatible.

        Matches existing constants: MAX_CONTEXT_CHUNKS=5, MAX_CHUNK_CONTENT=2000,
        MAX_ANSWER_LENGTH=2000, DEFAULT_RERANK_TOP_N=3.
        """
        return cls(
            query_type=QueryType.LOOKUP,
            hybrid_limit=50,
            rerank_top_n=3,
            max_context_chunks=5,
            max_chunk_content=2000,
            max_answer_length=2000,
            system_prompt_key="default",
        )

    @classmethod
    def for_summary(cls) -> "QueryProfile":
        """Summary queries — wider retrieval, structured prompt."""
        return cls(
            query_type=QueryType.SUMMARY,
            hybrid_limit=100,
            rerank_top_n=12,
            max_context_chunks=12,
            max_chunk_content=2000,
            max_answer_length=5000,
            system_prompt_key="summary",
        )

    @classmethod
    def for_comparison(cls) -> "QueryProfile":
        """Comparison queries — cross-document retrieval."""
        return cls(
            query_type=QueryType.COMPARISON,
            hybrid_limit=80,
            rerank_top_n=8,
            max_context_chunks=8,
            max_chunk_content=2000,
            max_answer_length=4000,
            system_prompt_key="default",
        )

    @classmethod
    def for_timeline(cls) -> "QueryProfile":
        """Timeline queries — moderate retrieval."""
        return cls(
            query_type=QueryType.TIMELINE,
            hybrid_limit=50,
            rerank_top_n=5,
            max_context_chunks=5,
            max_chunk_content=2000,
            max_answer_length=3000,
            system_prompt_key="default",
        )

    @classmethod
    def for_citation(cls) -> "QueryProfile":
        """Citation queries — moderate retrieval."""
        return cls(
            query_type=QueryType.CITATION,
            hybrid_limit=50,
            rerank_top_n=5,
            max_context_chunks=5,
            max_chunk_content=2000,
            max_answer_length=3000,
            system_prompt_key="default",
        )

    @classmethod
    def from_intent_signals(
        cls,
        signals: list,
        query: str,
    ) -> "QueryProfile":
        """Derive QueryProfile from intent classification + query text.

        Uses a combination of engine types from intent signals and keyword
        detection in the query text to select the appropriate profile.

        Args:
            signals: List of IntentSignal from MultiIntentAnalyzer.
            query: Original user query text.

        Returns:
            QueryProfile with appropriate parameters for this query type.
        """
        from app.models.orchestrator import EngineType

        engine_types = {s.engine for s in signals}
        query_lower = query.lower()

        # Check for summary sub-intent via keywords
        is_summary = any(kw in query_lower for kw in _SUMMARY_KEYWORDS)

        # Check for comparison sub-intent via keywords
        is_comparison = any(kw in query_lower for kw in _COMPARISON_KEYWORDS)

        if is_summary:
            profile = cls.for_summary()
        elif is_comparison or EngineType.CONTRADICTION in engine_types:
            profile = cls.for_comparison()
        elif EngineType.TIMELINE in engine_types:
            profile = cls.for_timeline()
        elif EngineType.CITATION in engine_types:
            profile = cls.for_citation()
        else:
            profile = cls.default()

        logger.info(
            "query_profile_selected",
            query_type=profile.query_type.value,
            rerank_top_n=profile.rerank_top_n,
            max_context_chunks=profile.max_context_chunks,
            max_answer_length=profile.max_answer_length,
            system_prompt_key=profile.system_prompt_key,
            is_summary=is_summary,
            is_comparison=is_comparison,
        )

        return profile
