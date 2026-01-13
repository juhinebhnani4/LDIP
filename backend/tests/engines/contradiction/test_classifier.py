"""Tests for Contradiction Classifier Engine.

Story 5-3: Contradiction Type Classification

Tests cover:
- Rule-based classification from EvidenceType (AC #1)
- Date mismatch classification with Indian formats (AC #2)
- Amount mismatch classification with Indian formats (AC #3)
- Semantic contradiction classification (AC #4)
- Factual contradiction classification
- LLM fallback when rule-based fails
- Value normalization (dates, amounts)
- Matter isolation security test
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.contradiction.classifier import (
    ClassificationCostTracker,
    ClassifierError,
    ContradictionClassifier,
    create_extracted_values,
    get_contradiction_classifier,
    normalize_indian_amount,
    normalize_indian_date,
)
from app.engines.contradiction.prompts import (
    format_classification_prompt,
    validate_classification_response,
)
from app.models.contradiction import (
    ComparisonResult,
    ContradictionEvidence,
    ContradictionType,
    EvidenceType,
    StatementPairComparison,
)

# =============================================================================
# Cost Tracker Tests
# =============================================================================


class TestClassificationCostTracker:
    """Tests for classification cost tracking."""

    def test_cost_zero_when_no_llm_used(self) -> None:
        """Should return zero cost when LLM not used (rule-based)."""
        tracker = ClassificationCostTracker(
            input_tokens=1000,
            output_tokens=500,
            used_llm=False,
        )
        assert tracker.cost_usd == 0.0

    def test_cost_calculated_when_llm_used(self) -> None:
        """Should calculate cost when LLM fallback is used."""
        tracker = ClassificationCostTracker(
            input_tokens=1000,
            output_tokens=500,
            used_llm=True,
        )
        # 1K input = $0.01, 0.5K output = $0.015
        expected = 0.01 + 0.015
        assert abs(tracker.cost_usd - expected) < 0.001

    def test_default_values(self) -> None:
        """Should default to zero tokens and no LLM."""
        tracker = ClassificationCostTracker()
        assert tracker.input_tokens == 0
        assert tracker.output_tokens == 0
        assert tracker.used_llm is False
        assert tracker.cost_usd == 0.0


# =============================================================================
# Value Normalization Tests (Indian Formats)
# =============================================================================


class TestNormalizeIndianAmount:
    """Tests for Indian amount normalization (AC #3)."""

    def test_normalize_lakhs(self) -> None:
        """Should normalize lakh amounts."""
        assert normalize_indian_amount("5 lakhs") == "500000"
        assert normalize_indian_amount("5 lakh") == "500000"
        assert normalize_indian_amount("10.5 lakhs") == "1050000"

    def test_normalize_crores(self) -> None:
        """Should normalize crore amounts."""
        assert normalize_indian_amount("2 crores") == "20000000"
        assert normalize_indian_amount("1.5 crore") == "15000000"

    def test_normalize_rupee_prefix(self) -> None:
        """Should normalize Rs. and ₹ prefixed amounts."""
        assert normalize_indian_amount("Rs. 50000") == "50000"
        assert normalize_indian_amount("Rs.50000") == "50000"
        assert normalize_indian_amount("INR 100000") == "100000"

    def test_normalize_indian_comma_format(self) -> None:
        """Should normalize Indian comma format (1,00,000)."""
        assert normalize_indian_amount("5,00,000") == "500000"
        assert normalize_indian_amount("1,50,000") == "150000"

    def test_normalize_plain_number(self) -> None:
        """Should handle plain numbers."""
        assert normalize_indian_amount("500000") == "500000"
        assert normalize_indian_amount("123.45") == "123.45"

    def test_normalize_none_input(self) -> None:
        """Should return None for None input."""
        assert normalize_indian_amount(None) is None

    def test_normalize_unparseable(self) -> None:
        """Should return None for unparseable strings."""
        assert normalize_indian_amount("no numbers here") is None


class TestNormalizeIndianDate:
    """Tests for Indian date normalization (AC #2)."""

    def test_normalize_dd_mm_yyyy_slash(self) -> None:
        """Should normalize DD/MM/YYYY format."""
        assert normalize_indian_date("15/01/2024") == "2024-01-15"
        assert normalize_indian_date("5/6/2024") == "2024-06-05"

    def test_normalize_dd_mm_yyyy_dash(self) -> None:
        """Should normalize DD-MM-YYYY format."""
        assert normalize_indian_date("15-01-2024") == "2024-01-15"
        assert normalize_indian_date("31-12-2023") == "2023-12-31"

    def test_normalize_dd_month_yyyy(self) -> None:
        """Should normalize DD Month YYYY format."""
        assert normalize_indian_date("15 January 2024") == "2024-01-15"
        assert normalize_indian_date("1 Dec 2023") == "2023-12-01"
        assert normalize_indian_date("5 Jun 2024") == "2024-06-05"

    def test_normalize_none_input(self) -> None:
        """Should return None for None input."""
        assert normalize_indian_date(None) is None

    def test_normalize_unparseable(self) -> None:
        """Should return None for unparseable strings."""
        assert normalize_indian_date("no date here") is None

    def test_normalize_invalid_date_values(self) -> None:
        """Should return None for invalid date values (Issue #3 fix)."""
        # Invalid month (13)
        assert normalize_indian_date("15/13/2024") is None
        # Invalid day (32)
        assert normalize_indian_date("32/01/2024") is None
        # Zero day/month
        assert normalize_indian_date("00/00/2024") is None
        # Day exceeds month's max (Feb 30)
        assert normalize_indian_date("30/02/2024") is None
        # Day exceeds month's max (Apr 31)
        assert normalize_indian_date("31/04/2024") is None

    def test_normalize_boundary_dates(self) -> None:
        """Should handle boundary date values correctly."""
        # Valid boundary dates
        assert normalize_indian_date("31/01/2024") == "2024-01-31"  # Jan has 31 days
        assert normalize_indian_date("28/02/2024") == "2024-02-28"  # Feb 28 valid
        assert normalize_indian_date("29/02/2024") == "2024-02-29"  # Feb 29 (leap year allowed)
        assert normalize_indian_date("30/04/2024") == "2024-04-30"  # Apr has 30 days


# =============================================================================
# Extracted Values Tests
# =============================================================================


class TestCreateExtractedValues:
    """Tests for creating extracted values structure."""

    def test_create_date_extracted_values(self) -> None:
        """Should create extracted values for date mismatch."""
        result = create_extracted_values(
            evidence_type=EvidenceType.DATE_MISMATCH,
            value_a="15/01/2024",
            value_b="15/06/2024",
        )

        assert result is not None
        assert result.value_a is not None
        assert result.value_a.original == "15/01/2024"
        assert result.value_a.normalized == "2024-01-15"
        assert result.value_b is not None
        assert result.value_b.original == "15/06/2024"
        assert result.value_b.normalized == "2024-06-15"

    def test_create_amount_extracted_values(self) -> None:
        """Should create extracted values for amount mismatch."""
        result = create_extracted_values(
            evidence_type=EvidenceType.AMOUNT_MISMATCH,
            value_a="5 lakhs",
            value_b="8 lakhs",
        )

        assert result is not None
        assert result.value_a is not None
        assert result.value_a.original == "5 lakhs"
        assert result.value_a.normalized == "500000"
        assert result.value_b is not None
        assert result.value_b.original == "8 lakhs"
        assert result.value_b.normalized == "800000"

    def test_create_no_values(self) -> None:
        """Should return None when no values provided."""
        result = create_extracted_values(
            evidence_type=EvidenceType.FACTUAL_CONFLICT,
            value_a=None,
            value_b=None,
        )
        assert result is None

    def test_create_partial_values(self) -> None:
        """Should handle partial values (one side only)."""
        result = create_extracted_values(
            evidence_type=EvidenceType.DATE_MISMATCH,
            value_a="15/01/2024",
            value_b=None,
        )

        assert result is not None
        assert result.value_a is not None
        assert result.value_b is None


# =============================================================================
# Prompt Formatting Tests
# =============================================================================


class TestClassificationPromptFormatting:
    """Tests for classification prompt construction."""

    def test_format_classification_prompt(self) -> None:
        """Should format prompt with all fields."""
        prompt = format_classification_prompt(
            content_a="The loan was Rs. 5 lakhs.",
            content_b="The loan was Rs. 8 lakhs.",
            reasoning="Amounts conflict: 5 lakhs vs 8 lakhs.",
        )

        assert "Rs. 5 lakhs" in prompt
        assert "Rs. 8 lakhs" in prompt
        assert "Amounts conflict" in prompt
        assert "contradiction_type" in prompt

    def test_validate_classification_response_valid(self) -> None:
        """Should pass validation for valid response."""
        parsed = {
            "contradiction_type": "amount_mismatch",
            "explanation": "Amounts differ",
            "confidence": 0.9,
        }
        errors = validate_classification_response(parsed)
        assert len(errors) == 0

    def test_validate_classification_response_invalid_type(self) -> None:
        """Should fail for invalid contradiction type."""
        parsed = {
            "contradiction_type": "invalid_type",
            "explanation": "Test",
            "confidence": 0.9,
        }
        errors = validate_classification_response(parsed)
        assert len(errors) > 0
        assert "invalid_type" in errors[0].lower() or "contradiction_type" in errors[0].lower()

    def test_validate_classification_response_missing_field(self) -> None:
        """Should fail for missing required fields."""
        parsed = {
            "contradiction_type": "date_mismatch",
            # Missing explanation and confidence
        }
        errors = validate_classification_response(parsed)
        assert len(errors) >= 2


# =============================================================================
# Contradiction Classifier Tests - Rule-Based Classification
# =============================================================================


class TestContradictionClassifierRuleBased:
    """Tests for rule-based classification (AC #1, #2, #3, #4)."""

    @pytest.fixture
    def classifier(self) -> ContradictionClassifier:
        """Create classifier instance."""
        with patch("app.engines.contradiction.classifier.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openai_api_key="test-key",
                openai_comparison_model="gpt-4-turbo-preview",
            )
            return ContradictionClassifier()

    @pytest.fixture
    def date_mismatch_comparison(self) -> StatementPairComparison:
        """Create comparison with date mismatch evidence (AC #2)."""
        return StatementPairComparison(
            statement_a_id="stmt-a",
            statement_b_id="stmt-b",
            statement_a_content="The loan was disbursed on 15/01/2024.",
            statement_b_content="The loan was disbursed on 15/06/2024.",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Statements conflict on disbursement date: 15/01/2024 vs 15/06/2024.",
            confidence=0.95,
            evidence=ContradictionEvidence(
                type=EvidenceType.DATE_MISMATCH,
                value_a="15/01/2024",
                value_b="15/06/2024",
            ),
            document_a_id="doc-1",
            document_b_id="doc-2",
        )

    @pytest.fixture
    def amount_mismatch_comparison(self) -> StatementPairComparison:
        """Create comparison with amount mismatch evidence (AC #3)."""
        return StatementPairComparison(
            statement_a_id="stmt-a",
            statement_b_id="stmt-b",
            statement_a_content="The loan amount was Rs. 5 lakhs.",
            statement_b_content="The loan amount was Rs. 8 lakhs.",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Statements conflict on loan amount: 5 lakhs vs 8 lakhs.",
            confidence=0.92,
            evidence=ContradictionEvidence(
                type=EvidenceType.AMOUNT_MISMATCH,
                value_a="5 lakhs",
                value_b="8 lakhs",
            ),
            document_a_id="doc-1",
            document_b_id="doc-2",
        )

    @pytest.fixture
    def semantic_comparison(self) -> StatementPairComparison:
        """Create comparison with semantic conflict evidence (AC #4)."""
        return StatementPairComparison(
            statement_a_id="stmt-a",
            statement_b_id="stmt-b",
            statement_a_content="Mr. Sharma was present at the signing ceremony.",
            statement_b_content="Mr. Sharma was not present during the signing.",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Semantic conflict: one states presence, other denies it.",
            confidence=0.88,
            evidence=ContradictionEvidence(
                type=EvidenceType.SEMANTIC_CONFLICT,
                value_a=None,
                value_b=None,
            ),
            document_a_id="doc-1",
            document_b_id="doc-2",
        )

    @pytest.fixture
    def factual_comparison(self) -> StatementPairComparison:
        """Create comparison with factual conflict evidence."""
        return StatementPairComparison(
            statement_a_id="stmt-a",
            statement_b_id="stmt-b",
            statement_a_content="The property is owned by Mr. Kumar.",
            statement_b_content="The property is owned by Mrs. Sharma.",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Direct factual conflict on property ownership.",
            confidence=0.90,
            evidence=ContradictionEvidence(
                type=EvidenceType.FACTUAL_CONFLICT,
                value_a="Mr. Kumar",
                value_b="Mrs. Sharma",
            ),
            document_a_id="doc-1",
            document_b_id="doc-2",
        )

    @pytest.mark.asyncio
    async def test_classify_date_mismatch(
        self,
        classifier: ContradictionClassifier,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should classify date mismatch contradiction (AC #2)."""
        result = await classifier.classify_contradiction(date_mismatch_comparison)

        # Verify classification type
        assert result.classified_contradiction.contradiction_type == ContradictionType.DATE_MISMATCH

        # Verify extracted values (AC #2: both dates extracted and displayed)
        assert result.classified_contradiction.extracted_values is not None
        assert result.classified_contradiction.extracted_values.value_a is not None
        assert result.classified_contradiction.extracted_values.value_a.original == "15/01/2024"
        assert result.classified_contradiction.extracted_values.value_a.normalized == "2024-01-15"
        assert result.classified_contradiction.extracted_values.value_b is not None
        assert result.classified_contradiction.extracted_values.value_b.original == "15/06/2024"
        assert result.classified_contradiction.extracted_values.value_b.normalized == "2024-06-15"

        # Verify rule-based (no LLM cost)
        assert result.llm_cost_usd == 0.0
        assert result.classified_contradiction.classification_method == "rule_based"

    @pytest.mark.asyncio
    async def test_classify_amount_mismatch_lakhs(
        self,
        classifier: ContradictionClassifier,
        amount_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should classify amount mismatch with Indian formats (AC #3)."""
        result = await classifier.classify_contradiction(amount_mismatch_comparison)

        # Verify classification type
        assert result.classified_contradiction.contradiction_type == ContradictionType.AMOUNT_MISMATCH

        # Verify extracted values (AC #3: both amounts extracted and displayed)
        assert result.classified_contradiction.extracted_values is not None
        assert result.classified_contradiction.extracted_values.value_a is not None
        assert result.classified_contradiction.extracted_values.value_a.original == "5 lakhs"
        assert result.classified_contradiction.extracted_values.value_a.normalized == "500000"
        assert result.classified_contradiction.extracted_values.value_b is not None
        assert result.classified_contradiction.extracted_values.value_b.original == "8 lakhs"
        assert result.classified_contradiction.extracted_values.value_b.normalized == "800000"

        # Verify rule-based
        assert result.llm_cost_usd == 0.0
        assert result.classified_contradiction.classification_method == "rule_based"

    @pytest.mark.asyncio
    async def test_classify_semantic_contradiction(
        self,
        classifier: ContradictionClassifier,
        semantic_comparison: StatementPairComparison,
    ) -> None:
        """Should classify semantic contradiction (AC #4)."""
        result = await classifier.classify_contradiction(semantic_comparison)

        # Verify classification type
        assert result.classified_contradiction.contradiction_type == ContradictionType.SEMANTIC_CONTRADICTION

        # Verify explanation highlights semantic conflict (AC #4)
        assert "semantic" in result.classified_contradiction.explanation.lower()

        # Verify rule-based
        assert result.llm_cost_usd == 0.0
        assert result.classified_contradiction.classification_method == "rule_based"

    @pytest.mark.asyncio
    async def test_classify_factual_contradiction(
        self,
        classifier: ContradictionClassifier,
        factual_comparison: StatementPairComparison,
    ) -> None:
        """Should classify factual contradiction."""
        result = await classifier.classify_contradiction(factual_comparison)

        # Verify classification type
        assert result.classified_contradiction.contradiction_type == ContradictionType.FACTUAL_CONTRADICTION

        # Verify rule-based
        assert result.llm_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_classify_non_contradiction_raises_error(
        self,
        classifier: ContradictionClassifier,
    ) -> None:
        """Should raise error when classifying non-contradiction."""
        consistent_comparison = StatementPairComparison(
            statement_a_id="stmt-a",
            statement_b_id="stmt-b",
            statement_a_content="Content A",
            statement_b_content="Content B",
            result=ComparisonResult.CONSISTENT,  # Not a contradiction
            reasoning="No conflict",
            confidence=0.9,
            evidence=ContradictionEvidence(type=EvidenceType.NONE),
            document_a_id="doc-1",
            document_b_id="doc-2",
        )

        with pytest.raises(ClassifierError) as exc_info:
            await classifier.classify_contradiction(consistent_comparison)

        assert "non-contradiction" in str(exc_info.value).lower()


# =============================================================================
# Contradiction Classifier Tests - LLM Fallback
# =============================================================================


class TestContradictionClassifierLLMFallback:
    """Tests for LLM fallback classification."""

    @pytest.fixture
    def classifier(self) -> ContradictionClassifier:
        """Create classifier instance."""
        with patch("app.engines.contradiction.classifier.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openai_api_key="test-key",
                openai_comparison_model="gpt-4-turbo-preview",
            )
            return ContradictionClassifier()

    @pytest.fixture
    def none_evidence_comparison(self) -> StatementPairComparison:
        """Create comparison with EvidenceType.NONE requiring LLM."""
        return StatementPairComparison(
            statement_a_id="stmt-a",
            statement_b_id="stmt-b",
            statement_a_content="The agreement was signed by both parties.",
            statement_b_content="The agreement was never signed.",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Statements conflict on whether agreement was signed.",
            confidence=0.85,
            evidence=ContradictionEvidence(
                type=EvidenceType.NONE,  # Triggers LLM fallback
                value_a=None,
                value_b=None,
            ),
            document_a_id="doc-1",
            document_b_id="doc-2",
        )

    @pytest.mark.asyncio
    async def test_llm_fallback_when_evidence_type_none(
        self,
        classifier: ContradictionClassifier,
        none_evidence_comparison: StatementPairComparison,
    ) -> None:
        """Should use LLM fallback when EvidenceType is NONE."""
        # Mock OpenAI client
        mock_client = AsyncMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = json.dumps({
            "contradiction_type": "factual_contradiction",
            "explanation": "Statements directly conflict on whether the agreement was signed.",
            "confidence": 0.9,
        })
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 300
        mock_completion.usage.completion_tokens = 100
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        classifier._client = mock_client

        result = await classifier.classify_contradiction(none_evidence_comparison)

        # Verify LLM was used
        assert result.classified_contradiction.classification_method == "llm_fallback"
        assert result.llm_cost_usd > 0

        # Verify classification
        assert result.classified_contradiction.contradiction_type == ContradictionType.FACTUAL_CONTRADICTION
        assert "signed" in result.classified_contradiction.explanation.lower()

    @pytest.mark.asyncio
    async def test_llm_fallback_graceful_degradation(
        self,
        classifier: ContradictionClassifier,
        none_evidence_comparison: StatementPairComparison,
    ) -> None:
        """Should fall back to semantic_contradiction on LLM error."""
        # Mock OpenAI client to fail
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        classifier._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await classifier.classify_contradiction(none_evidence_comparison)

        # Should default to semantic_contradiction on error
        assert result.classified_contradiction.contradiction_type == ContradictionType.SEMANTIC_CONTRADICTION
        assert "llm_fallback_error" in result.classified_contradiction.classification_method


# =============================================================================
# Batch Classification Tests
# =============================================================================


class TestBatchClassification:
    """Tests for batch classification of multiple comparisons."""

    @pytest.fixture
    def classifier(self) -> ContradictionClassifier:
        """Create classifier instance."""
        with patch("app.engines.contradiction.classifier.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openai_api_key="test-key",
                openai_comparison_model="gpt-4-turbo-preview",
            )
            return ContradictionClassifier()

    @pytest.mark.asyncio
    async def test_classify_all_filters_contradictions(
        self,
        classifier: ContradictionClassifier,
    ) -> None:
        """Should only classify contradiction results."""
        comparisons = [
            StatementPairComparison(
                statement_a_id="a1",
                statement_b_id="b1",
                statement_a_content="A",
                statement_b_content="B",
                result=ComparisonResult.CONTRADICTION,
                reasoning="Conflict",
                confidence=0.9,
                evidence=ContradictionEvidence(type=EvidenceType.DATE_MISMATCH, value_a="15/01/2024", value_b="15/06/2024"),
                document_a_id="d1",
                document_b_id="d2",
            ),
            StatementPairComparison(
                statement_a_id="a2",
                statement_b_id="b2",
                statement_a_content="C",
                statement_b_content="D",
                result=ComparisonResult.CONSISTENT,  # Not a contradiction
                reasoning="No conflict",
                confidence=0.9,
                evidence=ContradictionEvidence(type=EvidenceType.NONE),
                document_a_id="d1",
                document_b_id="d3",
            ),
            StatementPairComparison(
                statement_a_id="a3",
                statement_b_id="b3",
                statement_a_content="E",
                statement_b_content="F",
                result=ComparisonResult.CONTRADICTION,
                reasoning="Amount conflict",
                confidence=0.85,
                evidence=ContradictionEvidence(type=EvidenceType.AMOUNT_MISMATCH, value_a="5 lakhs", value_b="8 lakhs"),
                document_a_id="d2",
                document_b_id="d3",
            ),
        ]

        results = await classifier.classify_all(comparisons)

        # Should only have 2 results (contradictions only)
        assert len(results) == 2

        # Verify types
        types = [r.classified_contradiction.contradiction_type for r in results]
        assert ContradictionType.DATE_MISMATCH in types
        assert ContradictionType.AMOUNT_MISMATCH in types

    @pytest.mark.asyncio
    async def test_classify_all_empty_list(
        self,
        classifier: ContradictionClassifier,
    ) -> None:
        """Should handle empty comparison list."""
        results = await classifier.classify_all([])
        assert len(results) == 0


# =============================================================================
# Matter Isolation Tests (CRITICAL - Security)
# =============================================================================


class TestMatterIsolation:
    """Security tests for matter isolation."""

    @pytest.mark.asyncio
    async def test_classification_does_not_leak_cross_matter_data(self) -> None:
        """Should not allow cross-matter data access in classification.

        CRITICAL: Classification uses data from the comparison which
        should already be matter-scoped. This test verifies the classifier
        doesn't introduce new data access that could bypass RLS.
        """
        with patch("app.engines.contradiction.classifier.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openai_api_key="test-key",
                openai_comparison_model="gpt-4-turbo-preview",
            )

            classifier = ContradictionClassifier()

            # Create comparison from Matter A
            matter_a_comparison = StatementPairComparison(
                statement_a_id="matter-a-stmt-1",
                statement_b_id="matter-a-stmt-2",
                statement_a_content="Matter A content only",
                statement_b_content="More Matter A content",
                result=ComparisonResult.CONTRADICTION,
                reasoning="Matter A reasoning",
                confidence=0.9,
                evidence=ContradictionEvidence(
                    type=EvidenceType.FACTUAL_CONFLICT,
                    value_a="Value from Matter A",
                    value_b="Another value from Matter A",
                ),
                document_a_id="matter-a-doc-1",
                document_b_id="matter-a-doc-2",
            )

            result = await classifier.classify_contradiction(matter_a_comparison)

            # Verify output only contains Matter A data
            assert "matter-a-stmt-1" in result.classified_contradiction.comparison_id
            assert "matter-a-stmt-2" in result.classified_contradiction.comparison_id

            # Classifier should not access database or external data
            # All data comes from the input comparison
            assert "Matter A" in result.classified_contradiction.explanation or \
                   "Value from Matter A" in str(result.classified_contradiction.extracted_values)


# =============================================================================
# Factory Tests
# =============================================================================


class TestClassifierFactory:
    """Tests for classifier factory function."""

    def test_singleton_factory(self) -> None:
        """Should return singleton instance."""
        get_contradiction_classifier.cache_clear()

        with patch("app.engines.contradiction.classifier.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openai_api_key="test-key",
                openai_comparison_model="gpt-4-turbo-preview",
            )

            classifier1 = get_contradiction_classifier()
            classifier2 = get_contradiction_classifier()

            assert classifier1 is classifier2

        get_contradiction_classifier.cache_clear()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def classifier(self) -> ContradictionClassifier:
        """Create classifier instance."""
        with patch("app.engines.contradiction.classifier.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openai_api_key="test-key",
                openai_comparison_model="gpt-4-turbo-preview",
            )
            return ContradictionClassifier()

    def test_classification_map_completeness(self) -> None:
        """Verify all evidence types have mappings (except NONE)."""
        from app.engines.contradiction.classifier import CLASSIFICATION_MAP

        # All evidence types except NONE should have mappings
        for evidence_type in EvidenceType:
            if evidence_type != EvidenceType.NONE:
                assert evidence_type in CLASSIFICATION_MAP, f"Missing mapping for {evidence_type}"

    @pytest.mark.asyncio
    async def test_handle_empty_values(
        self,
        classifier: ContradictionClassifier,
    ) -> None:
        """Should handle comparisons with empty evidence values."""
        comparison = StatementPairComparison(
            statement_a_id="a",
            statement_b_id="b",
            statement_a_content="Content A",
            statement_b_content="Content B",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Semantic conflict",
            confidence=0.8,
            evidence=ContradictionEvidence(
                type=EvidenceType.SEMANTIC_CONFLICT,
                value_a=None,
                value_b=None,
            ),
            document_a_id="d1",
            document_b_id="d2",
        )

        result = await classifier.classify_contradiction(comparison)

        assert result.classified_contradiction.contradiction_type == ContradictionType.SEMANTIC_CONTRADICTION
        # Extracted values should be None for semantic conflicts without values
        # (This is acceptable - semantic conflicts don't have extractable values)

    @pytest.mark.asyncio
    async def test_normalize_amount_crores(
        self,
        classifier: ContradictionClassifier,
    ) -> None:
        """Should normalize crore amounts correctly."""
        comparison = StatementPairComparison(
            statement_a_id="a",
            statement_b_id="b",
            statement_a_content="Loan of 2 crores",
            statement_b_content="Loan of 3 crores",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Amount conflict",
            confidence=0.9,
            evidence=ContradictionEvidence(
                type=EvidenceType.AMOUNT_MISMATCH,
                value_a="2 crores",
                value_b="3 crores",
            ),
            document_a_id="d1",
            document_b_id="d2",
        )

        result = await classifier.classify_contradiction(comparison)

        assert result.classified_contradiction.extracted_values is not None
        assert result.classified_contradiction.extracted_values.value_a.normalized == "20000000"
        assert result.classified_contradiction.extracted_values.value_b.normalized == "30000000"
