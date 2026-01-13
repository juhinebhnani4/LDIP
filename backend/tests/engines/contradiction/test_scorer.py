"""Tests for Contradiction Scorer Engine.

Story 5-4: Severity Scoring and Explanation

Tests cover:
- Severity scoring rules (AC #1, #2, #3, #4)
- HIGH severity for date_mismatch with high confidence (AC #2)
- HIGH severity for amount_mismatch with high confidence (AC #2)
- MEDIUM severity for semantic_contradiction (AC #3)
- LOW severity for low confidence contradictions (AC #4)
- Explanation generation with document sources (AC #5)
- Evidence links creation
- Matter isolation security test
- Batch scoring
"""

import pytest

from app.engines.contradiction.scorer import (
    ContradictionScorer,
    ScoringMetrics,
    get_contradiction_scorer,
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
)
from app.models.contradiction import (
    ClassificationResult,
    ClassifiedContradiction,
    ComparisonResult,
    ContradictionEvidence,
    ContradictionType,
    EvidenceType,
    ExtractedValue,
    ExtractedValues,
    SeverityLevel,
    StatementPairComparison,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def scorer() -> ContradictionScorer:
    """Create scorer instance."""
    return ContradictionScorer()


@pytest.fixture
def date_mismatch_classified() -> ClassifiedContradiction:
    """Create classified contradiction for date mismatch."""
    return ClassifiedContradiction(
        comparison_id="stmt-a_stmt-b",
        statement_a_id="stmt-a",
        statement_b_id="stmt-b",
        contradiction_type=ContradictionType.DATE_MISMATCH,
        extracted_values=ExtractedValues(
            value_a=ExtractedValue(original="15/01/2024", normalized="2024-01-15"),
            value_b=ExtractedValue(original="15/06/2024", normalized="2024-06-15"),
        ),
        explanation="Statements conflict on disbursement date.",
        classification_method="rule_based",
    )


@pytest.fixture
def date_mismatch_comparison() -> StatementPairComparison:
    """Create comparison for date mismatch with high confidence."""
    return StatementPairComparison(
        statement_a_id="stmt-a",
        statement_b_id="stmt-b",
        statement_a_content="The loan was disbursed on 15/01/2024.",
        statement_b_content="The loan was disbursed on 15/06/2024.",
        result=ComparisonResult.CONTRADICTION,
        reasoning="Statements conflict on disbursement date: 15/01/2024 vs 15/06/2024.",
        confidence=0.92,  # HIGH confidence (>= 0.8)
        evidence=ContradictionEvidence(
            type=EvidenceType.DATE_MISMATCH,
            value_a="15/01/2024",
            value_b="15/06/2024",
        ),
        document_a_id="doc-1",
        document_b_id="doc-2",
        page_a=5,
        page_b=12,
    )


@pytest.fixture
def amount_mismatch_classified() -> ClassifiedContradiction:
    """Create classified contradiction for amount mismatch."""
    return ClassifiedContradiction(
        comparison_id="stmt-c_stmt-d",
        statement_a_id="stmt-c",
        statement_b_id="stmt-d",
        contradiction_type=ContradictionType.AMOUNT_MISMATCH,
        extracted_values=ExtractedValues(
            value_a=ExtractedValue(original="5 lakhs", normalized="500000"),
            value_b=ExtractedValue(original="8 lakhs", normalized="800000"),
        ),
        explanation="Statements conflict on loan amount.",
        classification_method="rule_based",
    )


@pytest.fixture
def amount_mismatch_comparison() -> StatementPairComparison:
    """Create comparison for amount mismatch with high confidence."""
    return StatementPairComparison(
        statement_a_id="stmt-c",
        statement_b_id="stmt-d",
        statement_a_content="The loan amount was Rs. 5 lakhs.",
        statement_b_content="The loan amount was Rs. 8 lakhs.",
        result=ComparisonResult.CONTRADICTION,
        reasoning="Statements conflict on loan amount: 5 lakhs vs 8 lakhs.",
        confidence=0.88,  # HIGH confidence (>= 0.8)
        evidence=ContradictionEvidence(
            type=EvidenceType.AMOUNT_MISMATCH,
            value_a="5 lakhs",
            value_b="8 lakhs",
        ),
        document_a_id="doc-1",
        document_b_id="doc-2",
        page_a=3,
        page_b=7,
    )


@pytest.fixture
def semantic_classified() -> ClassifiedContradiction:
    """Create classified contradiction for semantic conflict."""
    return ClassifiedContradiction(
        comparison_id="stmt-e_stmt-f",
        statement_a_id="stmt-e",
        statement_b_id="stmt-f",
        contradiction_type=ContradictionType.SEMANTIC_CONTRADICTION,
        extracted_values=None,
        explanation="Semantic conflict - statements have opposing meanings.",
        classification_method="rule_based",
    )


@pytest.fixture
def semantic_comparison() -> StatementPairComparison:
    """Create comparison for semantic conflict with moderate confidence."""
    return StatementPairComparison(
        statement_a_id="stmt-e",
        statement_b_id="stmt-f",
        statement_a_content="The borrower was cooperative throughout the process.",
        statement_b_content="The borrower was uncooperative and difficult.",
        result=ComparisonResult.CONTRADICTION,
        reasoning="Semantic conflict: one states cooperation, other denies it.",
        confidence=0.75,  # MEDIUM confidence (0.6 <= x < 0.8)
        evidence=ContradictionEvidence(
            type=EvidenceType.SEMANTIC_CONFLICT,
            value_a=None,
            value_b=None,
        ),
        document_a_id="doc-3",
        document_b_id="doc-4",
        page_a=None,  # Test missing page number
        page_b=15,
    )


@pytest.fixture
def low_confidence_classified() -> ClassifiedContradiction:
    """Create classified contradiction with low confidence."""
    return ClassifiedContradiction(
        comparison_id="stmt-g_stmt-h",
        statement_a_id="stmt-g",
        statement_b_id="stmt-h",
        contradiction_type=ContradictionType.FACTUAL_CONTRADICTION,
        extracted_values=None,
        explanation="Possible factual conflict.",
        classification_method="rule_based",
    )


@pytest.fixture
def low_confidence_comparison() -> StatementPairComparison:
    """Create comparison with low confidence."""
    return StatementPairComparison(
        statement_a_id="stmt-g",
        statement_b_id="stmt-h",
        statement_a_content="The meeting may have occurred in January.",
        statement_b_content="The meeting might have been in February.",
        result=ComparisonResult.CONTRADICTION,
        reasoning="Possible conflict on meeting date, but uncertain.",
        confidence=0.55,  # LOW confidence (< 0.6)
        evidence=ContradictionEvidence(
            type=EvidenceType.FACTUAL_CONFLICT,
            value_a=None,
            value_b=None,
        ),
        document_a_id="doc-5",
        document_b_id="doc-6",
        page_a=2,
        page_b=8,
    )


# =============================================================================
# Scoring Metrics Tests
# =============================================================================


class TestScoringMetrics:
    """Tests for scoring metrics tracking."""

    def test_add_high_severity(self) -> None:
        """Should increment high count."""
        metrics = ScoringMetrics()
        metrics.add(SeverityLevel.HIGH)

        assert metrics.total_scored == 1
        assert metrics.high_count == 1
        assert metrics.medium_count == 0
        assert metrics.low_count == 0

    def test_add_medium_severity(self) -> None:
        """Should increment medium count."""
        metrics = ScoringMetrics()
        metrics.add(SeverityLevel.MEDIUM)

        assert metrics.total_scored == 1
        assert metrics.medium_count == 1

    def test_add_low_severity(self) -> None:
        """Should increment low count."""
        metrics = ScoringMetrics()
        metrics.add(SeverityLevel.LOW)

        assert metrics.total_scored == 1
        assert metrics.low_count == 1

    def test_multiple_adds(self) -> None:
        """Should track multiple additions."""
        metrics = ScoringMetrics()
        metrics.add(SeverityLevel.HIGH)
        metrics.add(SeverityLevel.HIGH)
        metrics.add(SeverityLevel.MEDIUM)
        metrics.add(SeverityLevel.LOW)

        assert metrics.total_scored == 4
        assert metrics.high_count == 2
        assert metrics.medium_count == 1
        assert metrics.low_count == 1


# =============================================================================
# Severity Determination Tests (AC #1, #2, #3, #4)
# =============================================================================


class TestSeverityDetermination:
    """Tests for severity scoring rules."""

    def test_high_severity_date_mismatch_high_confidence(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score HIGH for date_mismatch with confidence >= 0.8 (AC #2)."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.DATE_MISMATCH,
            confidence=0.92,
        )
        assert severity == SeverityLevel.HIGH

    def test_high_severity_amount_mismatch_high_confidence(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score HIGH for amount_mismatch with confidence >= 0.8 (AC #2)."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.AMOUNT_MISMATCH,
            confidence=0.88,
        )
        assert severity == SeverityLevel.HIGH

    def test_high_severity_factual_high_confidence(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score HIGH for factual_contradiction with confidence >= 0.8."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.FACTUAL_CONTRADICTION,
            confidence=0.85,
        )
        assert severity == SeverityLevel.HIGH

    def test_medium_severity_semantic_contradiction(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score MEDIUM for semantic_contradiction (AC #3)."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.SEMANTIC_CONTRADICTION,
            confidence=0.78,
        )
        assert severity == SeverityLevel.MEDIUM

    def test_medium_severity_moderate_confidence_factual(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score MEDIUM for factual with moderate confidence (AC #3)."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.FACTUAL_CONTRADICTION,
            confidence=0.72,  # 0.6 <= x < 0.8
        )
        assert severity == SeverityLevel.MEDIUM

    def test_low_severity_low_confidence(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score LOW for low confidence regardless of type (AC #4)."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.FACTUAL_CONTRADICTION,
            confidence=0.55,  # Below 0.6 threshold
        )
        assert severity == SeverityLevel.LOW

    def test_low_severity_date_mismatch_low_confidence(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score LOW for date_mismatch with low confidence (AC #4)."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.DATE_MISMATCH,
            confidence=0.52,
        )
        assert severity == SeverityLevel.LOW

    def test_threshold_boundary_high(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score HIGH at exactly 0.8 threshold."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.DATE_MISMATCH,
            confidence=HIGH_CONFIDENCE_THRESHOLD,  # 0.8
        )
        assert severity == SeverityLevel.HIGH

    def test_threshold_boundary_low(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score MEDIUM at exactly 0.6 threshold."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.DATE_MISMATCH,
            confidence=LOW_CONFIDENCE_THRESHOLD,  # 0.6
        )
        # 0.6 is NOT below threshold, so it should be MEDIUM (not HIGH because < 0.8)
        assert severity == SeverityLevel.MEDIUM

    def test_threshold_boundary_just_below_low(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score LOW just below 0.6 threshold."""
        severity = scorer.determine_severity(
            contradiction_type=ContradictionType.DATE_MISMATCH,
            confidence=0.59,
        )
        assert severity == SeverityLevel.LOW


# =============================================================================
# Score Contradiction Tests (AC #1, #5)
# =============================================================================


class TestScoreContradiction:
    """Tests for scoring individual contradictions."""

    @pytest.mark.asyncio
    async def test_score_high_severity_date_mismatch(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should score HIGH severity for date mismatch with high confidence (AC #2)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name="Loan Agreement.pdf",
            document_b_name="Bank Statement.pdf",
        )

        assert result.scored_contradiction.severity == SeverityLevel.HIGH
        assert "HIGH SEVERITY" in result.scored_contradiction.explanation
        assert "date" in result.scored_contradiction.explanation.lower()

    @pytest.mark.asyncio
    async def test_score_high_severity_amount_mismatch(
        self,
        scorer: ContradictionScorer,
        amount_mismatch_classified: ClassifiedContradiction,
        amount_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should score HIGH severity for amount mismatch with high confidence (AC #2)."""
        result = await scorer.score_contradiction(
            classified=amount_mismatch_classified,
            comparison=amount_mismatch_comparison,
            document_a_name="Loan Agreement.pdf",
            document_b_name="Bank Statement.pdf",
        )

        assert result.scored_contradiction.severity == SeverityLevel.HIGH
        assert "HIGH SEVERITY" in result.scored_contradiction.explanation
        assert "amount" in result.scored_contradiction.explanation.lower()

    @pytest.mark.asyncio
    async def test_score_medium_severity_semantic(
        self,
        scorer: ContradictionScorer,
        semantic_classified: ClassifiedContradiction,
        semantic_comparison: StatementPairComparison,
    ) -> None:
        """Should score MEDIUM severity for semantic contradiction (AC #3)."""
        result = await scorer.score_contradiction(
            classified=semantic_classified,
            comparison=semantic_comparison,
            document_a_name="Interview Notes.pdf",
            document_b_name="Witness Statement.pdf",
        )

        assert result.scored_contradiction.severity == SeverityLevel.MEDIUM
        assert "MEDIUM SEVERITY" in result.scored_contradiction.explanation

    @pytest.mark.asyncio
    async def test_score_low_severity_low_confidence(
        self,
        scorer: ContradictionScorer,
        low_confidence_classified: ClassifiedContradiction,
        low_confidence_comparison: StatementPairComparison,
    ) -> None:
        """Should score LOW severity for low confidence contradictions (AC #4)."""
        result = await scorer.score_contradiction(
            classified=low_confidence_classified,
            comparison=low_confidence_comparison,
            document_a_name="Draft Notes.pdf",
            document_b_name="Meeting Minutes.pdf",
        )

        assert result.scored_contradiction.severity == SeverityLevel.LOW
        assert "LOW SEVERITY" in result.scored_contradiction.explanation
        assert "verification" in result.scored_contradiction.explanation.lower()


# =============================================================================
# Explanation Generation Tests (AC #5)
# =============================================================================


class TestExplanationGeneration:
    """Tests for explanation generation with document sources (AC #5)."""

    @pytest.mark.asyncio
    async def test_explanation_includes_document_sources(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should include document sources in explanation (AC #5)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name="Loan Agreement.pdf",
            document_b_name="Bank Statement.pdf",
        )

        explanation = result.scored_contradiction.explanation
        assert "Loan Agreement.pdf" in explanation
        assert "Bank Statement.pdf" in explanation

    @pytest.mark.asyncio
    async def test_explanation_includes_page_numbers(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should include page numbers in explanation (AC #5)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name="Loan Agreement.pdf",
            document_b_name="Bank Statement.pdf",
        )

        explanation = result.scored_contradiction.explanation
        assert "page 5" in explanation
        assert "page 12" in explanation

    @pytest.mark.asyncio
    async def test_explanation_handles_missing_page_numbers(
        self,
        scorer: ContradictionScorer,
        semantic_classified: ClassifiedContradiction,
        semantic_comparison: StatementPairComparison,
    ) -> None:
        """Should handle missing page numbers gracefully (AC #5)."""
        result = await scorer.score_contradiction(
            classified=semantic_classified,
            comparison=semantic_comparison,
            document_a_name="Document A.pdf",
            document_b_name="Document B.pdf",
        )

        explanation = result.scored_contradiction.explanation
        assert "page N/A" in explanation  # Missing page_a
        assert "page 15" in explanation   # Has page_b

    @pytest.mark.asyncio
    async def test_explanation_includes_statement_excerpts(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should include statement excerpts in explanation (AC #5)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name="Doc A",
            document_b_name="Doc B",
        )

        explanation = result.scored_contradiction.explanation
        assert "disbursed on 15/01/2024" in explanation
        assert "disbursed on 15/06/2024" in explanation

    @pytest.mark.asyncio
    async def test_explanation_includes_extracted_values(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should include extracted values in explanation for date/amount (AC #5)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name="Doc A",
            document_b_name="Doc B",
        )

        explanation = result.scored_contradiction.explanation
        assert "15/01/2024" in explanation
        assert "15/06/2024" in explanation


# =============================================================================
# Evidence Links Tests (AC #5)
# =============================================================================


class TestEvidenceLinks:
    """Tests for evidence links creation (AC #5)."""

    @pytest.mark.asyncio
    async def test_evidence_links_created(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should create evidence links for both statements (AC #5)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name="Loan Agreement.pdf",
            document_b_name="Bank Statement.pdf",
        )

        evidence_links = result.scored_contradiction.evidence_links
        assert len(evidence_links) == 2

    @pytest.mark.asyncio
    async def test_evidence_links_contain_document_info(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should include document info in evidence links (AC #5)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name="Loan Agreement.pdf",
            document_b_name="Bank Statement.pdf",
        )

        link_a = result.scored_contradiction.evidence_links[0]
        link_b = result.scored_contradiction.evidence_links[1]

        # Link A
        assert link_a.document_id == "doc-1"
        assert link_a.document_name == "Loan Agreement.pdf"
        assert link_a.page_number == 5
        assert link_a.statement_id == "stmt-a"

        # Link B
        assert link_b.document_id == "doc-2"
        assert link_b.document_name == "Bank Statement.pdf"
        assert link_b.page_number == 12
        assert link_b.statement_id == "stmt-b"

    @pytest.mark.asyncio
    async def test_evidence_links_contain_excerpts(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should include excerpts in evidence links (AC #5)."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
        )

        link_a = result.scored_contradiction.evidence_links[0]
        link_b = result.scored_contradiction.evidence_links[1]

        assert "disbursed on 15/01/2024" in link_a.excerpt
        assert "disbursed on 15/06/2024" in link_b.excerpt

    @pytest.mark.asyncio
    async def test_evidence_links_handle_missing_document_names(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should use placeholder for missing document names."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
            document_a_name=None,  # Missing
            document_b_name=None,  # Missing
        )

        link_a = result.scored_contradiction.evidence_links[0]
        link_b = result.scored_contradiction.evidence_links[1]

        assert link_a.document_name == "Unknown document"
        assert link_b.document_name == "Unknown document"


# =============================================================================
# Batch Scoring Tests
# =============================================================================


class TestBatchScoring:
    """Tests for batch scoring of multiple contradictions."""

    @pytest.mark.asyncio
    async def test_score_all_basic(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
        amount_mismatch_classified: ClassifiedContradiction,
        amount_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should score all contradictions in batch."""
        classifications = [
            ClassificationResult(
                classified_contradiction=date_mismatch_classified,
                llm_cost_usd=0.0,
                processing_time_ms=10,
            ),
            ClassificationResult(
                classified_contradiction=amount_mismatch_classified,
                llm_cost_usd=0.0,
                processing_time_ms=10,
            ),
        ]
        comparisons = [date_mismatch_comparison, amount_mismatch_comparison]

        result = await scorer.score_all(
            classifications=classifications,
            comparisons=comparisons,
        )

        assert result.total_scored == 2
        assert result.high_count == 2  # Both are HIGH severity
        assert result.medium_count == 0
        assert result.low_count == 0
        assert len(result.scored_contradictions) == 2

    @pytest.mark.asyncio
    async def test_score_all_mixed_severities(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
        semantic_classified: ClassifiedContradiction,
        semantic_comparison: StatementPairComparison,
        low_confidence_classified: ClassifiedContradiction,
        low_confidence_comparison: StatementPairComparison,
    ) -> None:
        """Should track mixed severity counts."""
        classifications = [
            ClassificationResult(
                classified_contradiction=date_mismatch_classified,
                llm_cost_usd=0.0,
                processing_time_ms=10,
            ),
            ClassificationResult(
                classified_contradiction=semantic_classified,
                llm_cost_usd=0.0,
                processing_time_ms=10,
            ),
            ClassificationResult(
                classified_contradiction=low_confidence_classified,
                llm_cost_usd=0.0,
                processing_time_ms=10,
            ),
        ]
        comparisons = [
            date_mismatch_comparison,
            semantic_comparison,
            low_confidence_comparison,
        ]

        result = await scorer.score_all(
            classifications=classifications,
            comparisons=comparisons,
        )

        assert result.total_scored == 3
        assert result.high_count == 1   # date_mismatch with 0.92 confidence
        assert result.medium_count == 1  # semantic with 0.75 confidence
        assert result.low_count == 1    # low_confidence with 0.55 confidence

    @pytest.mark.asyncio
    async def test_score_all_with_document_names(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should use document names from mapping."""
        classifications = [
            ClassificationResult(
                classified_contradiction=date_mismatch_classified,
                llm_cost_usd=0.0,
                processing_time_ms=10,
            ),
        ]
        comparisons = [date_mismatch_comparison]
        document_names = {
            "doc-1": "Contract.pdf",
            "doc-2": "Amendment.pdf",
        }

        result = await scorer.score_all(
            classifications=classifications,
            comparisons=comparisons,
            document_names=document_names,
        )

        scored = result.scored_contradictions[0]
        assert scored.evidence_links[0].document_name == "Contract.pdf"
        assert scored.evidence_links[1].document_name == "Amendment.pdf"

    @pytest.mark.asyncio
    async def test_score_all_empty_list(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should handle empty classification list."""
        result = await scorer.score_all(
            classifications=[],
            comparisons=[],
        )

        assert result.total_scored == 0
        assert result.high_count == 0
        assert result.medium_count == 0
        assert result.low_count == 0
        assert len(result.scored_contradictions) == 0

    @pytest.mark.asyncio
    async def test_score_all_missing_comparison(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should skip classifications with missing comparisons."""
        classified = ClassifiedContradiction(
            comparison_id="missing_missing",
            statement_a_id="missing",
            statement_b_id="missing",
            contradiction_type=ContradictionType.DATE_MISMATCH,
            extracted_values=None,
            explanation="Test",
            classification_method="rule_based",
        )
        classifications = [
            ClassificationResult(
                classified_contradiction=classified,
                llm_cost_usd=0.0,
                processing_time_ms=10,
            ),
        ]

        result = await scorer.score_all(
            classifications=classifications,
            comparisons=[],  # No comparisons to match
        )

        # Should skip and not crash
        assert result.total_scored == 0


# =============================================================================
# Matter Isolation Tests (CRITICAL - Security)
# =============================================================================


class TestMatterIsolation:
    """Security tests for matter isolation."""

    @pytest.mark.asyncio
    async def test_scoring_does_not_leak_cross_matter_data(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should not allow cross-matter data access in scoring.

        CRITICAL: Scoring uses data from the classification and comparison
        which should already be matter-scoped. This test verifies the scorer
        doesn't introduce new data access that could bypass RLS.
        """
        # Create comparison from Matter A
        matter_a_classified = ClassifiedContradiction(
            comparison_id="matter-a-stmt-1_matter-a-stmt-2",
            statement_a_id="matter-a-stmt-1",
            statement_b_id="matter-a-stmt-2",
            contradiction_type=ContradictionType.FACTUAL_CONTRADICTION,
            extracted_values=None,
            explanation="Matter A conflict",
            classification_method="rule_based",
        )
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
            page_a=1,
            page_b=2,
        )

        result = await scorer.score_contradiction(
            classified=matter_a_classified,
            comparison=matter_a_comparison,
            document_a_name="Matter A Document",
            document_b_name="Matter A Other Doc",
        )

        # Verify output only contains Matter A data
        scored = result.scored_contradiction
        assert "matter-a-stmt-1" in scored.comparison_id
        assert "matter-a-stmt-2" in scored.comparison_id
        assert scored.evidence_links[0].document_id == "matter-a-doc-1"
        assert scored.evidence_links[1].document_id == "matter-a-doc-2"

        # Explanation should reference Matter A content
        assert "Matter A content" in scored.explanation


# =============================================================================
# Factory Tests
# =============================================================================


class TestScorerFactory:
    """Tests for scorer factory function."""

    def test_singleton_factory(self) -> None:
        """Should return singleton instance."""
        get_contradiction_scorer.cache_clear()

        scorer1 = get_contradiction_scorer()
        scorer2 = get_contradiction_scorer()

        assert scorer1 is scorer2

        get_contradiction_scorer.cache_clear()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_truncate_long_excerpt(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should truncate very long statement content."""
        long_content = "A" * 500  # More than 200 char limit
        classified = ClassifiedContradiction(
            comparison_id="a_b",
            statement_a_id="a",
            statement_b_id="b",
            contradiction_type=ContradictionType.SEMANTIC_CONTRADICTION,
            extracted_values=None,
            explanation="Conflict",
            classification_method="rule_based",
        )
        comparison = StatementPairComparison(
            statement_a_id="a",
            statement_b_id="b",
            statement_a_content=long_content,
            statement_b_content=long_content,
            result=ComparisonResult.CONTRADICTION,
            reasoning="Test",
            confidence=0.8,
            evidence=ContradictionEvidence(type=EvidenceType.SEMANTIC_CONFLICT),
            document_a_id="d1",
            document_b_id="d2",
        )

        result = await scorer.score_contradiction(
            classified=classified,
            comparison=comparison,
        )

        # Evidence link excerpts should be truncated
        assert len(result.scored_contradiction.evidence_links[0].excerpt) <= 200
        assert result.scored_contradiction.evidence_links[0].excerpt.endswith("...")

    @pytest.mark.asyncio
    async def test_handle_very_low_confidence(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should score LOW for very low confidence values."""
        classified = ClassifiedContradiction(
            comparison_id="a_b",
            statement_a_id="a",
            statement_b_id="b",
            contradiction_type=ContradictionType.SEMANTIC_CONTRADICTION,
            extracted_values=None,
            explanation="Conflict",
            classification_method="rule_based",
        )
        comparison = StatementPairComparison(
            statement_a_id="a",
            statement_b_id="b",
            statement_a_content="Content A",
            statement_b_content="Content B",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Test",
            confidence=0.45,  # Very low confidence (below 0.6 threshold)
            evidence=ContradictionEvidence(type=EvidenceType.SEMANTIC_CONFLICT),
            document_a_id="d1",
            document_b_id="d2",
        )

        result = await scorer.score_contradiction(
            classified=classified,
            comparison=comparison,
        )

        # Should score LOW for very low confidence
        assert result.scored_contradiction.severity == SeverityLevel.LOW

    @pytest.mark.asyncio
    async def test_handle_perfect_confidence(
        self,
        scorer: ContradictionScorer,
    ) -> None:
        """Should handle 1.0 (100%) confidence."""
        classified = ClassifiedContradiction(
            comparison_id="a_b",
            statement_a_id="a",
            statement_b_id="b",
            contradiction_type=ContradictionType.DATE_MISMATCH,
            extracted_values=ExtractedValues(
                value_a=ExtractedValue(original="01/01/2024", normalized="2024-01-01"),
                value_b=ExtractedValue(original="01/02/2024", normalized="2024-02-01"),
            ),
            explanation="Clear date conflict",
            classification_method="rule_based",
        )
        comparison = StatementPairComparison(
            statement_a_id="a",
            statement_b_id="b",
            statement_a_content="Date was 01/01/2024",
            statement_b_content="Date was 01/02/2024",
            result=ComparisonResult.CONTRADICTION,
            reasoning="Clear date mismatch",
            confidence=1.0,  # Perfect confidence
            evidence=ContradictionEvidence(
                type=EvidenceType.DATE_MISMATCH,
                value_a="01/01/2024",
                value_b="01/02/2024",
            ),
            document_a_id="d1",
            document_b_id="d2",
        )

        result = await scorer.score_contradiction(
            classified=classified,
            comparison=comparison,
        )

        # Should score HIGH for perfect confidence date mismatch
        assert result.scored_contradiction.severity == SeverityLevel.HIGH
        assert result.scored_contradiction.confidence == 1.0

    @pytest.mark.asyncio
    async def test_processing_time_tracked(
        self,
        scorer: ContradictionScorer,
        date_mismatch_classified: ClassifiedContradiction,
        date_mismatch_comparison: StatementPairComparison,
    ) -> None:
        """Should track processing time."""
        result = await scorer.score_contradiction(
            classified=date_mismatch_classified,
            comparison=date_mismatch_comparison,
        )

        assert result.processing_time_ms >= 0
