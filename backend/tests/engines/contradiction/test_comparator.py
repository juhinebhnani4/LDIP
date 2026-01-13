"""Tests for Statement Comparator Engine.

Story 5-2: Statement Pair Comparison

Tests cover:
- Pair generation and deduplication (AC #1)
- Contradiction detection with amount/date mismatches (AC #2)
- Consistent pair handling (AC #3)
- Chain-of-thought reasoning capture (AC #4)
- GPT-4 response parsing
- Cost tracking
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.contradiction.comparator import (
    ComparisonBatchResult,
    ComparatorError,
    ComparisonParseError,
    LLMCostTracker,
    OpenAIConfigurationError,
    StatementComparator,
    StatementPair,
    get_statement_comparator,
)
from app.engines.contradiction.prompts import format_comparison_prompt
from app.models.contradiction import (
    ComparisonResult,
    DocumentStatements,
    EntityStatements,
    EvidenceType,
    Statement,
    StatementValue,
    StatementValueType,
)


# =============================================================================
# LLM Cost Tracker Tests
# =============================================================================


class TestLLMCostTracker:
    """Tests for LLM cost calculation."""

    def test_cost_calculation_input_only(self) -> None:
        """Should calculate cost for input tokens."""
        tracker = LLMCostTracker(input_tokens=1000, output_tokens=0)
        # $0.01 per 1K input tokens
        assert tracker.cost_usd == 0.01

    def test_cost_calculation_output_only(self) -> None:
        """Should calculate cost for output tokens."""
        tracker = LLMCostTracker(input_tokens=0, output_tokens=1000)
        # $0.03 per 1K output tokens
        assert tracker.cost_usd == 0.03

    def test_cost_calculation_combined(self) -> None:
        """Should calculate combined input + output cost."""
        tracker = LLMCostTracker(input_tokens=2000, output_tokens=500)
        # 2K input = $0.02, 0.5K output = $0.015
        expected = 0.02 + 0.015
        assert abs(tracker.cost_usd - expected) < 0.001

    def test_zero_tokens_zero_cost(self) -> None:
        """Should return zero cost for zero tokens."""
        tracker = LLMCostTracker()
        assert tracker.cost_usd == 0.0


# =============================================================================
# Comparison Batch Result Tests
# =============================================================================


class TestComparisonBatchResult:
    """Tests for batch result aggregation."""

    def test_empty_result(self) -> None:
        """Should handle empty results."""
        result = ComparisonBatchResult()
        assert result.total_cost_usd == 0.0
        assert result.contradictions_found == 0
        assert len(result.comparisons) == 0

    def test_contradictions_count(self) -> None:
        """Should count contradictions correctly."""
        from app.models.contradiction import (
            ContradictionEvidence,
            StatementPairComparison,
        )

        comparisons = [
            StatementPairComparison(
                statement_a_id="a1",
                statement_b_id="b1",
                statement_a_content="Content A",
                statement_b_content="Content B",
                result=ComparisonResult.CONTRADICTION,
                reasoning="Test",
                confidence=0.9,
                evidence=ContradictionEvidence(type=EvidenceType.AMOUNT_MISMATCH),
                document_a_id="doc1",
                document_b_id="doc2",
            ),
            StatementPairComparison(
                statement_a_id="a2",
                statement_b_id="b2",
                statement_a_content="Content C",
                statement_b_content="Content D",
                result=ComparisonResult.CONSISTENT,
                reasoning="Test",
                confidence=0.9,
                evidence=ContradictionEvidence(type=EvidenceType.NONE),
                document_a_id="doc1",
                document_b_id="doc3",
            ),
            StatementPairComparison(
                statement_a_id="a3",
                statement_b_id="b3",
                statement_a_content="Content E",
                statement_b_content="Content F",
                result=ComparisonResult.CONTRADICTION,
                reasoning="Test",
                confidence=0.8,
                evidence=ContradictionEvidence(type=EvidenceType.DATE_MISMATCH),
                document_a_id="doc2",
                document_b_id="doc3",
            ),
        ]

        result = ComparisonBatchResult(comparisons=comparisons)
        assert result.contradictions_found == 2


# =============================================================================
# Statement Pair Tests
# =============================================================================


class TestStatementPair:
    """Tests for StatementPair data class."""

    @pytest.fixture
    def sample_statement_a(self) -> Statement:
        """Create sample statement A."""
        return Statement(
            entity_id="entity-123",
            chunk_id="chunk-a",
            document_id="doc-1",
            content="The loan was Rs. 5 lakhs.",
            page_number=5,
        )

    @pytest.fixture
    def sample_statement_b(self) -> Statement:
        """Create sample statement B."""
        return Statement(
            entity_id="entity-123",
            chunk_id="chunk-b",
            document_id="doc-2",
            content="The loan was Rs. 8 lakhs.",
            page_number=12,
        )

    def test_pair_key_normalized(
        self,
        sample_statement_a: Statement,
        sample_statement_b: Statement,
    ) -> None:
        """Should normalize pair key (A,B) == (B,A)."""
        pair1 = StatementPair(
            statement_a=sample_statement_a,
            statement_b=sample_statement_b,
            entity_name="Test Entity",
        )
        pair2 = StatementPair(
            statement_a=sample_statement_b,
            statement_b=sample_statement_a,
            entity_name="Test Entity",
        )

        assert pair1.pair_key == pair2.pair_key

    def test_is_cross_document_true(
        self,
        sample_statement_a: Statement,
        sample_statement_b: Statement,
    ) -> None:
        """Should detect cross-document pairs."""
        pair = StatementPair(
            statement_a=sample_statement_a,
            statement_b=sample_statement_b,
            entity_name="Test Entity",
        )
        assert pair.is_cross_document() is True

    def test_is_cross_document_false(
        self,
        sample_statement_a: Statement,
    ) -> None:
        """Should detect same-document pairs."""
        same_doc_stmt = Statement(
            entity_id="entity-123",
            chunk_id="chunk-c",
            document_id="doc-1",  # Same as statement_a
            content="Another statement.",
            page_number=10,
        )

        pair = StatementPair(
            statement_a=sample_statement_a,
            statement_b=same_doc_stmt,
            entity_name="Test Entity",
        )
        assert pair.is_cross_document() is False


# =============================================================================
# Prompt Formatting Tests
# =============================================================================


class TestPromptFormatting:
    """Tests for prompt construction (AC #4)."""

    def test_format_comparison_prompt_basic(self) -> None:
        """Should format prompt with all fields."""
        prompt = format_comparison_prompt(
            entity_name="Nirav Jobalia",
            content_a="The loan was Rs. 5 lakhs.",
            content_b="The loan was Rs. 8 lakhs.",
            doc_a="Contract.pdf",
            doc_b="Statement.pdf",
            page_a=5,
            page_b=12,
        )

        assert "Nirav Jobalia" in prompt
        assert "Rs. 5 lakhs" in prompt
        assert "Rs. 8 lakhs" in prompt
        assert "Contract.pdf" in prompt
        assert "Statement.pdf" in prompt
        assert "page 5" in prompt
        assert "page 12" in prompt

    def test_format_comparison_prompt_unknown_pages(self) -> None:
        """Should handle unknown page numbers."""
        prompt = format_comparison_prompt(
            entity_name="Test",
            content_a="Content A",
            content_b="Content B",
            page_a=None,
            page_b=None,
        )

        assert "unknown" in prompt

    def test_format_comparison_prompt_json_schema(self) -> None:
        """Should include JSON response format."""
        prompt = format_comparison_prompt(
            entity_name="Test",
            content_a="A",
            content_b="B",
        )

        assert '"reasoning"' in prompt
        assert '"result"' in prompt
        assert '"confidence"' in prompt
        assert '"evidence"' in prompt


# =============================================================================
# Statement Comparator Tests
# =============================================================================


class TestStatementComparator:
    """Tests for StatementComparator engine."""

    @pytest.fixture
    def mock_openai_response(self) -> dict:
        """Create mock GPT-4 response for contradiction."""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "reasoning": "Statement A claims loan was Rs. 5 lakhs. Statement B claims Rs. 8 lakhs. These amounts conflict.",
                        "result": "contradiction",
                        "confidence": 0.95,
                        "evidence": {
                            "type": "amount_mismatch",
                            "value_a": "500000",
                            "value_b": "800000"
                        }
                    })
                }
            }],
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 150,
            }
        }

    @pytest.fixture
    def mock_consistent_response(self) -> dict:
        """Create mock GPT-4 response for consistent pair."""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "reasoning": "Both statements discuss the loan but from different perspectives. No conflict.",
                        "result": "consistent",
                        "confidence": 0.85,
                        "evidence": {
                            "type": "none",
                            "value_a": None,
                            "value_b": None
                        }
                    })
                }
            }],
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 100,
            }
        }

    def test_init_without_api_key(self) -> None:
        """Should raise error when API key not configured."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="")
            comparator = StatementComparator()

            with pytest.raises(OpenAIConfigurationError):
                _ = comparator.client

    @pytest.mark.asyncio
    async def test_compare_statement_pair_contradiction(
        self,
        mock_openai_response: dict,
    ) -> None:
        """Should detect contradiction with amount mismatch (AC #2)."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            # Mock OpenAI client
            mock_client = AsyncMock()
            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = mock_openai_response["choices"][0]["message"]["content"]
            mock_completion.usage = MagicMock()
            mock_completion.usage.prompt_tokens = 500
            mock_completion.usage.completion_tokens = 150
            mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
            comparator._client = mock_client

            stmt_a = Statement(
                entity_id="entity-123",
                chunk_id="chunk-a",
                document_id="doc-1",
                content="The loan was Rs. 5 lakhs.",
                page_number=5,
            )
            stmt_b = Statement(
                entity_id="entity-123",
                chunk_id="chunk-b",
                document_id="doc-2",
                content="The loan was Rs. 8 lakhs.",
                page_number=12,
            )

            comparison, cost_tracker = await comparator.compare_statement_pair(
                statement_a=stmt_a,
                statement_b=stmt_b,
                entity_name="Nirav Jobalia",
            )

            # Verify contradiction detected (AC #2)
            assert comparison.result == ComparisonResult.CONTRADICTION
            assert comparison.evidence.type == EvidenceType.AMOUNT_MISMATCH
            assert comparison.confidence == 0.95

            # Verify reasoning captured (AC #4)
            assert "Rs. 5 lakhs" in comparison.reasoning or "500000" in comparison.reasoning

            # Verify cost tracking
            assert cost_tracker.input_tokens == 500
            assert cost_tracker.output_tokens == 150
            assert cost_tracker.cost_usd > 0

    @pytest.mark.asyncio
    async def test_compare_statement_pair_consistent(
        self,
        mock_consistent_response: dict,
    ) -> None:
        """Should mark consistent pairs as consistent (AC #3)."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            mock_client = AsyncMock()
            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = mock_consistent_response["choices"][0]["message"]["content"]
            mock_completion.usage = MagicMock()
            mock_completion.usage.prompt_tokens = 500
            mock_completion.usage.completion_tokens = 100
            mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
            comparator._client = mock_client

            stmt_a = Statement(
                entity_id="entity-123",
                chunk_id="chunk-a",
                document_id="doc-1",
                content="The borrower took a loan.",
                page_number=5,
            )
            stmt_b = Statement(
                entity_id="entity-123",
                chunk_id="chunk-b",
                document_id="doc-2",
                content="The loan was used for business purposes.",
                page_number=12,
            )

            comparison, _ = await comparator.compare_statement_pair(
                statement_a=stmt_a,
                statement_b=stmt_b,
                entity_name="Test Entity",
            )

            # Verify consistent classification (AC #3)
            assert comparison.result == ComparisonResult.CONSISTENT
            assert comparison.evidence.type == EvidenceType.NONE

    def test_parse_comparison_response_valid(self) -> None:
        """Should parse valid GPT-4 JSON response."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            response_text = json.dumps({
                "reasoning": "Test reasoning",
                "result": "contradiction",
                "confidence": 0.9,
                "evidence": {
                    "type": "date_mismatch",
                    "value_a": "2024-01-15",
                    "value_b": "2024-06-20"
                }
            })

            stmt_a = Statement(
                entity_id="e1", chunk_id="c1", document_id="d1",
                content="A", page_number=1,
            )
            stmt_b = Statement(
                entity_id="e1", chunk_id="c2", document_id="d2",
                content="B", page_number=2,
            )

            result = comparator._parse_comparison_response(response_text, stmt_a, stmt_b)

            assert result.result == ComparisonResult.CONTRADICTION
            assert result.evidence.type == EvidenceType.DATE_MISMATCH
            assert result.evidence.value_a == "2024-01-15"
            assert result.evidence.value_b == "2024-06-20"

    def test_parse_comparison_response_invalid_json(self) -> None:
        """Should raise error for invalid JSON."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            stmt = Statement(
                entity_id="e1", chunk_id="c1", document_id="d1",
                content="A", page_number=1,
            )

            with pytest.raises(ComparisonParseError):
                comparator._parse_comparison_response("not json", stmt, stmt)


# =============================================================================
# Pair Generation Tests (AC #1)
# =============================================================================


class TestPairGeneration:
    """Tests for unique pair generation."""

    @pytest.fixture
    def entity_statements(self) -> EntityStatements:
        """Create entity statements with multiple documents."""
        return EntityStatements(
            entity_id="entity-123",
            entity_name="Nirav Jobalia",
            total_statements=4,
            documents=[
                DocumentStatements(
                    document_id="doc-1",
                    document_name="Contract.pdf",
                    statements=[
                        Statement(
                            entity_id="entity-123",
                            chunk_id="chunk-1",
                            document_id="doc-1",
                            content="Statement 1 from doc 1",
                            page_number=1,
                        ),
                        Statement(
                            entity_id="entity-123",
                            chunk_id="chunk-2",
                            document_id="doc-1",
                            content="Statement 2 from doc 1",
                            page_number=2,
                        ),
                    ],
                    statement_count=2,
                ),
                DocumentStatements(
                    document_id="doc-2",
                    document_name="Statement.pdf",
                    statements=[
                        Statement(
                            entity_id="entity-123",
                            chunk_id="chunk-3",
                            document_id="doc-2",
                            content="Statement 1 from doc 2",
                            page_number=5,
                        ),
                        Statement(
                            entity_id="entity-123",
                            chunk_id="chunk-4",
                            document_id="doc-2",
                            content="Statement 2 from doc 2",
                            page_number=6,
                        ),
                    ],
                    statement_count=2,
                ),
            ],
            aliases_included=[],
        )

    def test_generate_pairs_cross_document_only(
        self,
        entity_statements: EntityStatements,
    ) -> None:
        """Should only generate cross-document pairs when flag is True."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            pairs = comparator._generate_statement_pairs(
                entity_statements=entity_statements,
                max_pairs=100,
                cross_document_only=True,
            )

            # 2 statements from doc-1 x 2 statements from doc-2 = 4 cross-doc pairs
            assert len(pairs) == 4

            # Verify all pairs are cross-document
            for pair in pairs:
                assert pair.is_cross_document()

    def test_generate_pairs_include_same_document(
        self,
        entity_statements: EntityStatements,
    ) -> None:
        """Should include same-document pairs when flag is False."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            pairs = comparator._generate_statement_pairs(
                entity_statements=entity_statements,
                max_pairs=100,
                cross_document_only=False,
            )

            # 4 statements total -> 4*3/2 = 6 unique pairs
            assert len(pairs) == 6

    def test_generate_pairs_respects_max_pairs(
        self,
        entity_statements: EntityStatements,
    ) -> None:
        """Should respect max_pairs limit."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            pairs = comparator._generate_statement_pairs(
                entity_statements=entity_statements,
                max_pairs=2,
                cross_document_only=False,
            )

            assert len(pairs) == 2

    def test_generate_pairs_deduplication(
        self,
        entity_statements: EntityStatements,
    ) -> None:
        """Should not generate duplicate pairs (A,B) == (B,A)."""
        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator = StatementComparator()

            pairs = comparator._generate_statement_pairs(
                entity_statements=entity_statements,
                max_pairs=100,
                cross_document_only=False,
            )

            # Check for uniqueness
            pair_keys = [p.pair_key for p in pairs]
            assert len(pair_keys) == len(set(pair_keys))


# =============================================================================
# Factory Tests
# =============================================================================


class TestComparatorFactory:
    """Tests for comparator factory function."""

    def test_singleton_factory(self) -> None:
        """Should return singleton instance."""
        get_statement_comparator.cache_clear()

        with patch("app.engines.contradiction.comparator.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(openai_api_key="test-key")

            comparator1 = get_statement_comparator()
            comparator2 = get_statement_comparator()

            assert comparator1 is comparator2

        get_statement_comparator.cache_clear()
