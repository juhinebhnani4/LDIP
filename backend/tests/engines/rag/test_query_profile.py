"""Tests for QueryProfile matter-size-aware scaling.

Covers:
- _scale_for_matter_size tier boundaries (small/medium/large)
- Minimum clamps on all parameters
- from_intent_signals with document_count integration
- Edge cases: 0 docs, boundary values, None document_count
"""

from unittest.mock import MagicMock

from app.engines.rag.query_profile import QueryProfile, QueryType

# =============================================================================
# _scale_for_matter_size
# =============================================================================


class TestScaleForMatterSize:
    """Tests for the _scale_for_matter_size class method."""

    def test_small_matter_applies_50_percent_scale(self):
        """Matters with <=10 docs get 50% scaling on hybrid_limit only."""
        profile = QueryProfile.for_summary()  # 100, 12, 12, 5000
        scaled = QueryProfile._scale_for_matter_size(profile, 5)

        assert scaled.hybrid_limit == 50  # 100 * 0.5
        # Quality params preserved (not scaled)
        assert scaled.rerank_top_n == 12
        assert scaled.max_context_chunks == 12
        assert scaled.max_answer_length == 5000

    def test_medium_matter_applies_70_percent_scale(self):
        """Matters with 11-30 docs get 70% scaling on hybrid_limit only."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 28)

        assert scaled.hybrid_limit == 70  # 100 * 0.7
        # Quality params preserved (not scaled)
        assert scaled.rerank_top_n == 12
        assert scaled.max_context_chunks == 12
        assert scaled.max_answer_length == 5000

    def test_large_matter_returns_original(self):
        """Matters with 31+ docs keep original parameters."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 50)

        assert scaled is profile  # Same object — no copy made
        assert scaled.hybrid_limit == 100
        assert scaled.rerank_top_n == 12
        assert scaled.max_context_chunks == 12
        assert scaled.max_answer_length == 5000

    def test_boundary_10_docs_is_small(self):
        """Exactly 10 docs falls in the small tier."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 10)

        assert scaled.hybrid_limit == 50  # Small tier (50%)

    def test_boundary_11_docs_is_medium(self):
        """Exactly 11 docs falls in the medium tier."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 11)

        assert scaled.hybrid_limit == 70  # Medium tier (70%)

    def test_boundary_30_docs_is_medium(self):
        """Exactly 30 docs falls in the medium tier."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 30)

        assert scaled.hybrid_limit == 70  # Medium tier (70%)

    def test_boundary_31_docs_is_large(self):
        """Exactly 31 docs falls in the large tier."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 31)

        assert scaled is profile  # Unchanged

    def test_zero_docs_uses_small_tier(self):
        """0 documents (new matter, all processing) uses small tier."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 0)

        assert scaled.hybrid_limit == 50

    def test_minimum_clamps_on_small_default_profile(self):
        """Small default profile (50, 5, 6, 2000) — quality params preserved."""
        profile = QueryProfile.default()  # 50, 5, 6, 2000
        scaled = QueryProfile._scale_for_matter_size(profile, 3)

        assert scaled.hybrid_limit == 25  # 50 * 0.5 = 25 (>= 20 min)
        # Quality params preserved (not scaled)
        assert scaled.rerank_top_n == 5
        assert scaled.max_context_chunks == 6
        assert scaled.max_answer_length == 2000

    def test_preserves_query_type(self):
        """Scaled profile keeps the original query type."""
        profile = QueryProfile.for_comparison()
        scaled = QueryProfile._scale_for_matter_size(profile, 5)

        assert scaled.query_type == QueryType.COMPARISON

    def test_preserves_system_prompt_key(self):
        """Scaled profile keeps the original system prompt key."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 5)

        assert scaled.system_prompt_key == "summary"

    def test_preserves_search_weights(self):
        """Scaled profile keeps the original search weights."""
        profile = QueryProfile.for_citation()
        scaled = QueryProfile._scale_for_matter_size(profile, 5)

        assert scaled.search_weights.bm25 == 1.5
        assert scaled.search_weights.semantic == 0.7

    def test_preserves_max_chunk_content(self):
        """max_chunk_content is never scaled."""
        profile = QueryProfile.for_summary()
        scaled = QueryProfile._scale_for_matter_size(profile, 5)

        assert scaled.max_chunk_content == 2000  # Always preserved


# =============================================================================
# from_intent_signals with document_count
# =============================================================================


class TestFromIntentSignalsWithDocumentCount:
    """Tests for from_intent_signals document_count integration."""

    def _make_rag_signal(self):
        """Create a minimal RAG intent signal."""
        from app.models.orchestrator import EngineType
        signal = MagicMock()
        signal.engine = EngineType.RAG
        return signal

    def _make_timeline_signal(self):
        from app.models.orchestrator import EngineType
        signal = MagicMock()
        signal.engine = EngineType.TIMELINE
        return signal

    def _make_contradiction_signal(self):
        from app.models.orchestrator import EngineType
        signal = MagicMock()
        signal.engine = EngineType.CONTRADICTION
        return signal

    def test_no_document_count_uses_full_parameters(self):
        """When document_count is None, no scaling applied (backward compat)."""
        signals = [self._make_rag_signal()]
        profile = QueryProfile.from_intent_signals(signals, "summarize this case")

        # Should be for_summary with no scaling
        assert profile.query_type == QueryType.SUMMARY
        assert profile.hybrid_limit == 100
        assert profile.rerank_top_n == 12

    def test_summary_with_small_matter(self):
        """Summary query + small matter = scaled hybrid_limit, preserved quality."""
        signals = [self._make_rag_signal()]
        profile = QueryProfile.from_intent_signals(
            signals, "summarize the allegations", document_count=5
        )

        assert profile.query_type == QueryType.SUMMARY
        assert profile.hybrid_limit == 50  # 100 * 0.5
        assert profile.rerank_top_n == 12  # Preserved (not scaled)

    def test_summary_with_large_matter(self):
        """Summary query + large matter = original parameters."""
        signals = [self._make_rag_signal()]
        profile = QueryProfile.from_intent_signals(
            signals, "give me a summary", document_count=50
        )

        assert profile.hybrid_limit == 100
        assert profile.rerank_top_n == 12

    def test_comparison_with_medium_matter(self):
        """Comparison query + medium matter = 70% scaling."""
        signals = [self._make_contradiction_signal()]
        profile = QueryProfile.from_intent_signals(
            signals, "what are the key points", document_count=20
        )

        assert profile.query_type == QueryType.COMPARISON
        assert profile.hybrid_limit == 56  # int(80 * 0.7)

    def test_default_query_with_small_matter(self):
        """Default/lookup query + small matter — only hybrid_limit scaled."""
        signals = [self._make_rag_signal()]
        profile = QueryProfile.from_intent_signals(
            signals, "who is the petitioner", document_count=3
        )

        assert profile.query_type == QueryType.LOOKUP
        assert profile.hybrid_limit == 25  # int(50 * 0.5)
        assert profile.rerank_top_n == 5   # Preserved (default profile value)

    def test_timeline_with_medium_matter(self):
        """Timeline query + medium matter."""
        signals = [self._make_timeline_signal()]
        profile = QueryProfile.from_intent_signals(
            signals, "what is the timeline", document_count=15
        )

        assert profile.query_type == QueryType.TIMELINE
        assert profile.hybrid_limit == 35  # int(50 * 0.7)

    def test_document_count_zero(self):
        """Edge case: 0 searchable documents."""
        signals = [self._make_rag_signal()]
        profile = QueryProfile.from_intent_signals(
            signals, "summarize everything", document_count=0
        )

        assert profile.query_type == QueryType.SUMMARY
        assert profile.hybrid_limit == 50  # Small tier
