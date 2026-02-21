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

import re
from dataclasses import dataclass
from enum import Enum

import structlog

from app.services.rag.hybrid_search import SearchWeights

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


# Keywords used to detect summary sub-intent from query text.
# "brief" is excluded — too common in legal contexts ("amicus brief", "reply brief")
# and causes false positives that trigger summary retrieval for specific queries.
_SUMMARY_KEYWORDS = frozenset([
    "summarize", "summary", "key findings", "overview", "gist",
    "main points", "highlights", "recap", "outline",
])

# Keywords used to detect comparison sub-intent from query text
_COMPARISON_KEYWORDS = frozenset([
    "compare", "comparison", "contrast", "versus", "vs",
    "differ", "difference", "differences",
])

# Compiled word-boundary patterns for keyword matching.
# Using word boundaries (\b) prevents substring false positives like
# "outlined" matching "outline" or "different" matching "differ".
_SUMMARY_PATTERNS = [re.compile(rf"\b{re.escape(kw)}\b") for kw in _SUMMARY_KEYWORDS]
_COMPARISON_PATTERNS = [re.compile(rf"\b{re.escape(kw)}\b") for kw in _COMPARISON_KEYWORDS]


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
    search_weights: SearchWeights = SearchWeights()

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
            search_weights=SearchWeights(bm25=1.0, semantic=1.0),
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
            search_weights=SearchWeights(bm25=0.7, semantic=1.3),
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
            search_weights=SearchWeights(bm25=0.8, semantic=1.2),
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
            search_weights=SearchWeights(bm25=1.0, semantic=1.0),
        )

    @classmethod
    def for_citation(cls) -> "QueryProfile":
        """Citation queries — higher BM25 for exact legal references."""
        return cls(
            query_type=QueryType.CITATION,
            hybrid_limit=50,
            rerank_top_n=5,
            max_context_chunks=5,
            max_chunk_content=2000,
            max_answer_length=3000,
            system_prompt_key="default",
            search_weights=SearchWeights(bm25=1.5, semantic=0.7),
        )

    @classmethod
    def _scale_for_matter_size(cls, profile: "QueryProfile", document_count: int) -> "QueryProfile":
        """Scale retrieval parameters based on matter size.

        Small matters don't need massive candidate pools — pulling 100
        candidates from a corpus of 200 chunks is wasteful. This scales
        parameters proportionally so small matters are fast while large
        matters still get thorough retrieval.

        Args:
            profile: Base profile from query type classification.
            document_count: Number of documents in the matter.

        Returns:
            New QueryProfile with scaled parameters (frozen dataclass).
        """
        if document_count <= 10:
            scale = 0.5
            tier = "small"
        elif document_count <= 30:
            scale = 0.7
            tier = "medium"
        else:
            # Large matters keep original parameters
            return profile

        scaled = cls(
            query_type=profile.query_type,
            hybrid_limit=max(20, int(profile.hybrid_limit * scale)),
            rerank_top_n=max(3, int(profile.rerank_top_n * scale)),
            max_context_chunks=max(3, int(profile.max_context_chunks * scale)),
            max_chunk_content=profile.max_chunk_content,
            max_answer_length=max(1500, int(profile.max_answer_length * scale)),
            system_prompt_key=profile.system_prompt_key,
            search_weights=profile.search_weights,
        )

        logger.info(
            "query_profile_scaled_for_matter_size",
            tier=tier,
            document_count=document_count,
            original_hybrid_limit=profile.hybrid_limit,
            scaled_hybrid_limit=scaled.hybrid_limit,
            original_rerank_top_n=profile.rerank_top_n,
            scaled_rerank_top_n=scaled.rerank_top_n,
        )

        return scaled

    @classmethod
    def from_intent_signals(
        cls,
        signals: list,
        query: str,
        document_count: int | None = None,
    ) -> "QueryProfile":
        """Derive QueryProfile from intent classification + query text.

        Uses a combination of engine types from intent signals and keyword
        detection in the query text to select the appropriate profile.
        If document_count is provided, scales parameters based on matter size.

        Args:
            signals: List of IntentSignal from MultiIntentAnalyzer.
            query: Original user query text.
            document_count: Number of documents in the matter (optional).

        Returns:
            QueryProfile with appropriate parameters for this query type.
        """
        from app.models.orchestrator import EngineType

        engine_types = {s.engine for s in signals}
        query_lower = query.lower()

        # Check for summary sub-intent via word-boundary keyword matching.
        # Word boundaries prevent false positives from legal terms like
        # "amicus brief", "outlined", or substring matches.
        is_summary = any(p.search(query_lower) for p in _SUMMARY_PATTERNS)

        # Check for comparison sub-intent via word-boundary keyword matching
        is_comparison = any(p.search(query_lower) for p in _COMPARISON_PATTERNS)

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

        # Scale parameters based on matter size if document count is known
        if document_count is not None:
            profile = cls._scale_for_matter_size(profile, document_count)

        logger.info(
            "query_profile_selected",
            query_type=profile.query_type.value,
            rerank_top_n=profile.rerank_top_n,
            max_context_chunks=profile.max_context_chunks,
            max_answer_length=profile.max_answer_length,
            system_prompt_key=profile.system_prompt_key,
            bm25_weight=profile.search_weights.bm25,
            semantic_weight=profile.search_weights.semantic,
            is_summary=is_summary,
            is_comparison=is_comparison,
            document_count=document_count,
        )

        return profile
