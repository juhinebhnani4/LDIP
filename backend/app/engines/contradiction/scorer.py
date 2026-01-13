"""Contradiction Scorer Engine for severity scoring and explanation generation.

Story 5-4: Severity Scoring and Explanation

Final stage of the Contradiction Engine pipeline. Scores contradictions by severity
(HIGH, MEDIUM, LOW) and generates attorney-ready explanations with document references.

CRITICAL: This is 100% rule-based - NO LLM calls. Cost: $0 for all operations.
"""

import time
from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.models.contradiction import (
    ClassificationResult,
    ClassifiedContradiction,
    ContradictionType,
    EvidenceLink,
    ExtractedValues,
    ScoredContradiction,
    ScoringBatchResult,
    ScoringResult,
    SeverityLevel,
    StatementPairComparison,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Confidence thresholds for severity scoring (Story 5-4 Dev Notes)
HIGH_CONFIDENCE_THRESHOLD = 0.8
LOW_CONFIDENCE_THRESHOLD = 0.6

# Default confidence when missing (MEDIUM range)
DEFAULT_CONFIDENCE = 0.7

# Maximum excerpt length for evidence links
MAX_EXCERPT_LENGTH = 200

# Contradiction types that are HIGH severity when confidence >= 0.8
HIGH_SEVERITY_TYPES = {
    ContradictionType.DATE_MISMATCH,
    ContradictionType.AMOUNT_MISMATCH,
    ContradictionType.FACTUAL_CONTRADICTION,
}


# =============================================================================
# Explanation Templates (Story 5-4 Dev Notes)
# =============================================================================

EXPLANATION_TEMPLATES = {
    SeverityLevel.HIGH: {
        ContradictionType.DATE_MISMATCH: (
            "HIGH SEVERITY: Date conflict detected.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "The documents show dates of '{value_a}' vs '{value_b}' - "
            "a significant discrepancy requiring immediate review."
        ),
        ContradictionType.AMOUNT_MISMATCH: (
            "HIGH SEVERITY: Amount conflict detected.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "The amounts of {value_a} vs {value_b} represent "
            "a significant financial discrepancy requiring immediate review."
        ),
        ContradictionType.FACTUAL_CONTRADICTION: (
            "HIGH SEVERITY: Direct factual conflict detected.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "These statements make directly conflicting factual claims "
            "that require immediate attorney review."
        ),
        ContradictionType.SEMANTIC_CONTRADICTION: (
            "HIGH SEVERITY: Significant semantic conflict detected.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "These statements have opposing meanings that require attorney review."
        ),
    },
    SeverityLevel.MEDIUM: {
        ContradictionType.DATE_MISMATCH: (
            "MEDIUM SEVERITY: Possible date conflict.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "The documents may show conflicting dates of '{value_a}' vs '{value_b}'. "
            "Review recommended to confirm discrepancy."
        ),
        ContradictionType.AMOUNT_MISMATCH: (
            "MEDIUM SEVERITY: Possible amount conflict.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "The amounts of {value_a} vs {value_b} may indicate a financial discrepancy. "
            "Review recommended."
        ),
        ContradictionType.FACTUAL_CONTRADICTION: (
            "MEDIUM SEVERITY: Possible factual conflict.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "These statements may make conflicting claims. Review recommended."
        ),
        ContradictionType.SEMANTIC_CONTRADICTION: (
            "MEDIUM SEVERITY: Semantic conflict detected.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "These statements have potentially opposing meanings. "
            "Interpretation may vary - review recommended."
        ),
    },
    SeverityLevel.LOW: {
        ContradictionType.DATE_MISMATCH: (
            "LOW SEVERITY: Uncertain date conflict.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "Possible date discrepancy of '{value_a}' vs '{value_b}', but confidence is low. "
            "Verification recommended before acting on this finding."
        ),
        ContradictionType.AMOUNT_MISMATCH: (
            "LOW SEVERITY: Uncertain amount conflict.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "Possible amount discrepancy of {value_a} vs {value_b}, but confidence is low. "
            "Verification recommended before acting on this finding."
        ),
        ContradictionType.FACTUAL_CONTRADICTION: (
            "LOW SEVERITY: Uncertain factual conflict.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "These statements may conflict, but analysis is uncertain. "
            "Verification recommended."
        ),
        ContradictionType.SEMANTIC_CONTRADICTION: (
            "LOW SEVERITY: Possible semantic conflict.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "These statements may have different meanings, but analysis is uncertain. "
            "Verification recommended before drawing conclusions."
        ),
    },
}


# Severity reasoning templates
SEVERITY_REASONING = {
    SeverityLevel.HIGH: {
        ContradictionType.DATE_MISMATCH: (
            "Date conflict with high confidence ({confidence:.0%}). "
            "Clear factual discrepancy requiring immediate attention."
        ),
        ContradictionType.AMOUNT_MISMATCH: (
            "Amount conflict with high confidence ({confidence:.0%}). "
            "Financial discrepancy requiring immediate attention."
        ),
        ContradictionType.FACTUAL_CONTRADICTION: (
            "Direct factual conflict with high confidence ({confidence:.0%}). "
            "Clear disagreement on material facts."
        ),
        ContradictionType.SEMANTIC_CONTRADICTION: (
            "Significant semantic conflict with high confidence ({confidence:.0%})."
        ),
    },
    SeverityLevel.MEDIUM: {
        ContradictionType.DATE_MISMATCH: (
            "Date conflict with moderate confidence ({confidence:.0%}). "
            "May require interpretation."
        ),
        ContradictionType.AMOUNT_MISMATCH: (
            "Amount conflict with moderate confidence ({confidence:.0%}). "
            "May require interpretation."
        ),
        ContradictionType.FACTUAL_CONTRADICTION: (
            "Factual conflict with moderate confidence ({confidence:.0%}). "
            "May require interpretation."
        ),
        ContradictionType.SEMANTIC_CONTRADICTION: (
            "Semantic conflict detected ({confidence:.0%}). "
            "Statements have potentially opposing meanings."
        ),
    },
    SeverityLevel.LOW: {
        ContradictionType.DATE_MISMATCH: (
            "Date conflict with low confidence ({confidence:.0%}). "
            "Uncertain analysis - verification needed."
        ),
        ContradictionType.AMOUNT_MISMATCH: (
            "Amount conflict with low confidence ({confidence:.0%}). "
            "Uncertain analysis - verification needed."
        ),
        ContradictionType.FACTUAL_CONTRADICTION: (
            "Factual conflict with low confidence ({confidence:.0%}). "
            "Uncertain analysis - verification needed."
        ),
        ContradictionType.SEMANTIC_CONTRADICTION: (
            "Semantic conflict with low confidence ({confidence:.0%}). "
            "Uncertain analysis - verification needed."
        ),
    },
}


# =============================================================================
# Scoring Metrics
# =============================================================================


@dataclass
class ScoringMetrics:
    """Track scoring operation metrics (for monitoring, not cost - always $0)."""

    total_scored: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    processing_time_ms: int = 0

    def add(self, severity: SeverityLevel) -> None:
        """Record a scored contradiction."""
        self.total_scored += 1
        match severity:
            case SeverityLevel.HIGH:
                self.high_count += 1
            case SeverityLevel.MEDIUM:
                self.medium_count += 1
            case SeverityLevel.LOW:
                self.low_count += 1


# =============================================================================
# Contradiction Scorer Engine
# =============================================================================


class ContradictionScorer:
    """Engine for scoring contradictions by severity and generating explanations.

    Story 5-4: Final stage of the Contradiction Engine pipeline.

    Pipeline:
    1. STATEMENT QUERYING (5-1) -> 2. PAIR COMPARISON (5-2) ->
    3. CLASSIFICATION (5-3) -> 4. SEVERITY SCORING (5-4) 👈

    Scoring Strategy:
    - 100% rule-based using ContradictionType and confidence
    - NO LLM calls required
    - Cost: $0 for all scoring operations

    Example:
        >>> scorer = ContradictionScorer()
        >>> result = await scorer.score_contradiction(classified, comparison)
        >>> result.scored_contradiction.severity
        SeverityLevel.HIGH
    """

    def __init__(self) -> None:
        """Initialize contradiction scorer."""
        logger.info("contradiction_scorer_initialized")

    def determine_severity(
        self,
        contradiction_type: ContradictionType,
        confidence: float,
    ) -> SeverityLevel:
        """Determine severity level based on contradiction type and confidence.

        Story 5-4: Rule-based severity determination.

        Args:
            contradiction_type: Classification from Story 5-3.
            confidence: Confidence score from comparison (0-1).

        Returns:
            SeverityLevel (HIGH, MEDIUM, or LOW).

        Scoring Rules:
            - HIGH: Clear factual types (DATE_MISMATCH, AMOUNT_MISMATCH,
                   FACTUAL_CONTRADICTION) with confidence >= 0.8
            - LOW: Any type with confidence < 0.6
            - MEDIUM: Everything else (semantic, or moderate confidence)
        """
        # LOW: Low confidence regardless of type
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            return SeverityLevel.LOW

        # HIGH: Clear factual differences with high confidence
        if (
            contradiction_type in HIGH_SEVERITY_TYPES
            and confidence >= HIGH_CONFIDENCE_THRESHOLD
        ):
            return SeverityLevel.HIGH

        # MEDIUM: Everything else (semantic, or moderate confidence)
        return SeverityLevel.MEDIUM

    def _truncate_excerpt(self, content: str) -> str:
        """Truncate content to maximum excerpt length.

        Args:
            content: Full statement content.

        Returns:
            Truncated content with ellipsis if needed.
        """
        if len(content) <= MAX_EXCERPT_LENGTH:
            return content
        return content[: MAX_EXCERPT_LENGTH - 3] + "..."

    def _create_evidence_link(
        self,
        statement_id: str,
        document_id: str,
        document_name: str | None,
        page_number: int | None,
        content: str,
    ) -> EvidenceLink:
        """Create an evidence link for a statement.

        Args:
            statement_id: Chunk ID reference.
            document_id: Document UUID.
            document_name: Document filename (or placeholder if missing).
            page_number: Page reference.
            content: Statement content for excerpt.

        Returns:
            EvidenceLink with all references.
        """
        return EvidenceLink(
            statement_id=statement_id,
            document_id=document_id,
            document_name=document_name or "Unknown document",
            page_number=page_number,
            excerpt=self._truncate_excerpt(content),
            bbox_ids=[],  # Future: populated from bounding box data
        )

    def _generate_severity_reasoning(
        self,
        severity: SeverityLevel,
        contradiction_type: ContradictionType,
        confidence: float,
    ) -> str:
        """Generate brief reasoning for severity assignment.

        Args:
            severity: Assigned severity level.
            contradiction_type: Classification type.
            confidence: Confidence score.

        Returns:
            Brief reasoning string.
        """
        template = SEVERITY_REASONING.get(severity, {}).get(
            contradiction_type,
            "Conflict detected with confidence {confidence:.0%}.",
        )
        return template.format(confidence=confidence)

    def _generate_explanation(
        self,
        severity: SeverityLevel,
        contradiction_type: ContradictionType,
        comparison: StatementPairComparison,
        extracted_values: ExtractedValues | None,
        document_a_name: str | None,
        document_b_name: str | None,
    ) -> str:
        """Generate attorney-ready explanation with document references.

        Story 5-4: Template-based explanation generation (no LLM).

        Args:
            severity: Assigned severity level.
            contradiction_type: Classification type.
            comparison: Original comparison with statement content.
            extracted_values: Extracted date/amount values.
            document_a_name: Document A filename.
            document_b_name: Document B filename.

        Returns:
            Formatted explanation string.
        """
        template = EXPLANATION_TEMPLATES.get(severity, {}).get(
            contradiction_type,
            (
                "{severity_upper} SEVERITY: Conflict detected.\n\n"
                "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
                "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
                "These statements conflict. Review recommended."
            ),
        )

        # Extract values for display
        value_a = ""
        value_b = ""
        if extracted_values:
            if extracted_values.value_a:
                value_a = extracted_values.value_a.original
            if extracted_values.value_b:
                value_b = extracted_values.value_b.original

        # Format page numbers (use "N/A" if not available)
        page_a = str(comparison.page_a) if comparison.page_a is not None else "N/A"
        page_b = str(comparison.page_b) if comparison.page_b is not None else "N/A"

        return template.format(
            severity_upper=severity.value.upper(),
            doc_a=document_a_name or "Unknown document",
            doc_b=document_b_name or "Unknown document",
            page_a=page_a,
            page_b=page_b,
            excerpt_a=self._truncate_excerpt(comparison.statement_a_content),
            excerpt_b=self._truncate_excerpt(comparison.statement_b_content),
            value_a=value_a,
            value_b=value_b,
        )

    async def score_contradiction(
        self,
        classified: ClassifiedContradiction,
        comparison: StatementPairComparison,
        document_a_name: str | None = None,
        document_b_name: str | None = None,
    ) -> ScoringResult:
        """Score a single classified contradiction.

        Story 5-4: Main scoring entry point.

        Args:
            classified: ClassifiedContradiction from classifier (Story 5-3).
            comparison: Original StatementPairComparison with statement content.
            document_a_name: Optional document A filename for display.
            document_b_name: Optional document B filename for display.

        Returns:
            ScoringResult with scored contradiction and metadata.
        """
        start_time = time.time()

        # Get confidence from comparison (default if missing)
        confidence = comparison.confidence if comparison.confidence else DEFAULT_CONFIDENCE

        # Determine severity
        severity = self.determine_severity(
            contradiction_type=classified.contradiction_type,
            confidence=confidence,
        )

        # Generate severity reasoning
        severity_reasoning = self._generate_severity_reasoning(
            severity=severity,
            contradiction_type=classified.contradiction_type,
            confidence=confidence,
        )

        # Create evidence links for both statements
        evidence_link_a = self._create_evidence_link(
            statement_id=comparison.statement_a_id,
            document_id=comparison.document_a_id,
            document_name=document_a_name,
            page_number=comparison.page_a,
            content=comparison.statement_a_content,
        )
        evidence_link_b = self._create_evidence_link(
            statement_id=comparison.statement_b_id,
            document_id=comparison.document_b_id,
            document_name=document_b_name,
            page_number=comparison.page_b,
            content=comparison.statement_b_content,
        )

        # Generate attorney-ready explanation
        explanation = self._generate_explanation(
            severity=severity,
            contradiction_type=classified.contradiction_type,
            comparison=comparison,
            extracted_values=classified.extracted_values,
            document_a_name=document_a_name,
            document_b_name=document_b_name,
        )

        # Create scored contradiction
        scored = ScoredContradiction(
            comparison_id=classified.comparison_id,
            statement_a_id=classified.statement_a_id,
            statement_b_id=classified.statement_b_id,
            contradiction_type=classified.contradiction_type,
            severity=severity,
            severity_reasoning=severity_reasoning,
            explanation=explanation,
            evidence_links=[evidence_link_a, evidence_link_b],
            extracted_values=classified.extracted_values,
            confidence=confidence,
        )

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "contradiction_scored",
            comparison_id=classified.comparison_id,
            contradiction_type=classified.contradiction_type.value,
            severity=severity.value,
            confidence=confidence,
            processing_time_ms=processing_time,
        )

        return ScoringResult(
            scored_contradiction=scored,
            processing_time_ms=processing_time,
        )

    async def score_all(
        self,
        classifications: list[ClassificationResult],
        comparisons: list[StatementPairComparison],
        document_names: dict[str, str] | None = None,
    ) -> ScoringBatchResult:
        """Score all classified contradictions in a batch.

        Story 5-4: Batch scoring for post-classification processing.

        Args:
            classifications: List of ClassificationResults from classifier.
            comparisons: Original comparisons (for matching by comparison_id).
            document_names: Optional mapping of document_id -> document_name.

        Returns:
            ScoringBatchResult with all scored contradictions and counts.
        """
        start_time = time.time()
        metrics = ScoringMetrics()

        # Build comparison lookup by statement pair
        comparison_map: dict[str, StatementPairComparison] = {}
        for comp in comparisons:
            key = f"{comp.statement_a_id}_{comp.statement_b_id}"
            comparison_map[key] = comp

        document_names = document_names or {}
        scored_contradictions: list[ScoredContradiction] = []

        for classification in classifications:
            classified = classification.classified_contradiction

            # Find matching comparison
            comparison = comparison_map.get(classified.comparison_id)
            if not comparison:
                logger.warning(
                    "scoring_comparison_not_found",
                    comparison_id=classified.comparison_id,
                )
                continue

            # Get document names for display
            doc_a_name = document_names.get(comparison.document_a_id)
            doc_b_name = document_names.get(comparison.document_b_id)

            # Score the contradiction
            result = await self.score_contradiction(
                classified=classified,
                comparison=comparison,
                document_a_name=doc_a_name,
                document_b_name=doc_b_name,
            )

            scored_contradictions.append(result.scored_contradiction)
            metrics.add(result.scored_contradiction.severity)

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "batch_scoring_complete",
            total_scored=metrics.total_scored,
            high_count=metrics.high_count,
            medium_count=metrics.medium_count,
            low_count=metrics.low_count,
            processing_time_ms=processing_time,
        )

        return ScoringBatchResult(
            scored_contradictions=scored_contradictions,
            total_scored=metrics.total_scored,
            high_count=metrics.high_count,
            medium_count=metrics.medium_count,
            low_count=metrics.low_count,
            processing_time_ms=processing_time,
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_contradiction_scorer() -> ContradictionScorer:
    """Get singleton contradiction scorer instance.

    Returns:
        ContradictionScorer instance.
    """
    return ContradictionScorer()
