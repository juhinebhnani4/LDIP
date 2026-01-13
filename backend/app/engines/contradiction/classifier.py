"""Contradiction Classifier Engine for type classification.

Story 5-3: Contradiction Type Classification

Classifies contradictions by type (date_mismatch, amount_mismatch, factual,
semantic) for attorney prioritization. Uses rule-based classification first,
with GPT-4 fallback only for ambiguous cases.

CRITICAL: Minimize LLM usage - 80%+ should be rule-based, <20% LLM.
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.engines.contradiction.prompts import (
    CLASSIFICATION_ENHANCEMENT_SYSTEM_PROMPT,
    format_classification_prompt,
    validate_classification_response,
)
from app.models.contradiction import (
    ClassificationResult,
    ClassifiedContradiction,
    ComparisonResult,
    ContradictionType,
    EvidenceType,
    ExtractedValue,
    ExtractedValues,
    StatementPairComparison,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# EvidenceType to ContradictionType mapping (Story 5-3 Dev Notes)
CLASSIFICATION_MAP: dict[EvidenceType, ContradictionType] = {
    EvidenceType.DATE_MISMATCH: ContradictionType.DATE_MISMATCH,
    EvidenceType.AMOUNT_MISMATCH: ContradictionType.AMOUNT_MISMATCH,
    EvidenceType.FACTUAL_CONFLICT: ContradictionType.FACTUAL_CONTRADICTION,
    EvidenceType.SEMANTIC_CONFLICT: ContradictionType.SEMANTIC_CONTRADICTION,
}

# GPT-4 Turbo pricing (same as comparator)
# NOTE: These are approximate costs for GPT-4 Turbo (gpt-4-turbo-preview).
# Actual costs may vary based on openai_comparison_model setting in config.
# Update these constants if using a different model (e.g., GPT-4o, GPT-4-mini).
GPT4_INPUT_COST_PER_1K = 0.01
GPT4_OUTPUT_COST_PER_1K = 0.03

# Retry settings
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0

# Indian amount patterns for normalization
INDIAN_AMOUNT_PATTERNS = [
    # Lakhs patterns
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|lakhs|lacs)", re.IGNORECASE), 100000),
    # Crores patterns
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)", re.IGNORECASE), 10000000),
    # Rs./INR prefix patterns
    (re.compile(r"(?:Rs\.?|INR|₹)\s*(\d+(?:,\d{2,3})*(?:\.\d+)?)", re.IGNORECASE), 1),
    # Plain numbers with commas (Indian format: 1,00,000)
    (re.compile(r"(\d{1,2},(?:\d{2},)*\d{3}(?:\.\d+)?)"), 1),
]

# Date patterns for normalization (Indian formats)
INDIAN_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})"),
    # DD Month YYYY
    re.compile(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(\d{4})",
        re.IGNORECASE,
    ),
]

MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}


# =============================================================================
# Cost Tracking
# =============================================================================


@dataclass
class ClassificationCostTracker:
    """Track LLM costs for classification (only when fallback is used)."""

    input_tokens: int = 0
    output_tokens: int = 0
    used_llm: bool = False

    @property
    def cost_usd(self) -> float:
        """Calculate total cost in USD."""
        if not self.used_llm:
            return 0.0
        input_cost = (self.input_tokens / 1000) * GPT4_INPUT_COST_PER_1K
        output_cost = (self.output_tokens / 1000) * GPT4_OUTPUT_COST_PER_1K
        return input_cost + output_cost


# =============================================================================
# Exceptions
# =============================================================================


class ClassifierError(Exception):
    """Base exception for classifier operations."""

    def __init__(
        self,
        message: str,
        code: str = "CLASSIFIER_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class ClassificationParseError(ClassifierError):
    """Raised when GPT-4 response cannot be parsed."""

    def __init__(self, message: str):
        super().__init__(message, code="PARSE_ERROR", is_retryable=True)


# =============================================================================
# Value Normalization Utilities
# =============================================================================


def normalize_indian_amount(value: str | None) -> str | None:
    """Normalize Indian amount format to numeric string.

    Args:
        value: Original amount string (e.g., "5 lakhs", "Rs. 50,00,000").

    Returns:
        Normalized numeric string or None if cannot parse.
    """
    if not value:
        return None

    for pattern, multiplier in INDIAN_AMOUNT_PATTERNS:
        match = pattern.search(value)
        if match:
            num_str = match.group(1).replace(",", "")
            try:
                num = float(num_str) * multiplier
                # Return as integer string if whole number
                if num == int(num):
                    return str(int(num))
                return str(num)
            except ValueError:
                continue

    # Try to extract plain number
    plain_match = re.search(r"(\d+(?:\.\d+)?)", value)
    if plain_match:
        return plain_match.group(1)

    return None


def _is_valid_date(day: int, month: int, year: int) -> bool:
    """Validate date components are within reasonable ranges.

    Args:
        day: Day of month (1-31).
        month: Month (1-12).
        year: Year (1900-2100 for legal documents).

    Returns:
        True if date components are valid.
    """
    if month < 1 or month > 12:
        return False
    if day < 1 or day > 31:
        return False
    if year < 1900 or year > 2100:
        return False
    # Basic month-day validation (not accounting for leap years)
    days_in_month = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return day <= days_in_month[month]


def normalize_indian_date(value: str | None) -> str | None:
    """Normalize Indian date format to ISO 8601 (YYYY-MM-DD).

    Args:
        value: Original date string (e.g., "15/01/2024", "15 Jan 2024").

    Returns:
        Normalized ISO date string or None if cannot parse or invalid.
    """
    if not value:
        return None

    # Try DD/MM/YYYY or DD-MM-YYYY pattern
    pattern1 = INDIAN_DATE_PATTERNS[0]
    match = pattern1.search(value)
    if match:
        day, month, year = match.groups()
        try:
            day_int, month_int, year_int = int(day), int(month), int(year)
            if not _is_valid_date(day_int, month_int, year_int):
                return None
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except ValueError:
            return None

    # Try DD Month YYYY pattern
    pattern2 = INDIAN_DATE_PATTERNS[1]
    match = pattern2.search(value)
    if match:
        day, month_name, year = match.groups()
        month = MONTH_MAP.get(month_name.lower()[:3], "01")
        try:
            day_int, month_int, year_int = int(day), int(month), int(year)
            if not _is_valid_date(day_int, month_int, year_int):
                return None
            return f"{year}-{month}-{day.zfill(2)}"
        except ValueError:
            return None

    return None


def create_extracted_values(
    evidence_type: EvidenceType,
    value_a: str | None,
    value_b: str | None,
) -> ExtractedValues | None:
    """Create structured extracted values from evidence.

    Story 5-3: Format values for attorney display with original and normalized forms.

    Args:
        evidence_type: Type of evidence (determines normalization).
        value_a: Original value from statement A.
        value_b: Original value from statement B.

    Returns:
        ExtractedValues or None if no values to extract.
    """
    if not value_a and not value_b:
        return None

    extracted_a: ExtractedValue | None = None
    extracted_b: ExtractedValue | None = None

    match evidence_type:
        case EvidenceType.DATE_MISMATCH:
            if value_a:
                normalized_a = normalize_indian_date(value_a)
                extracted_a = ExtractedValue(
                    original=value_a,
                    normalized=normalized_a or value_a,
                )
            if value_b:
                normalized_b = normalize_indian_date(value_b)
                extracted_b = ExtractedValue(
                    original=value_b,
                    normalized=normalized_b or value_b,
                )

        case EvidenceType.AMOUNT_MISMATCH:
            if value_a:
                normalized_a = normalize_indian_amount(value_a)
                extracted_a = ExtractedValue(
                    original=value_a,
                    normalized=normalized_a or value_a,
                )
            if value_b:
                normalized_b = normalize_indian_amount(value_b)
                extracted_b = ExtractedValue(
                    original=value_b,
                    normalized=normalized_b or value_b,
                )

        case _:
            # For other types, use values as-is if present
            if value_a:
                extracted_a = ExtractedValue(original=value_a, normalized=value_a)
            if value_b:
                extracted_b = ExtractedValue(original=value_b, normalized=value_b)

    if extracted_a or extracted_b:
        return ExtractedValues(value_a=extracted_a, value_b=extracted_b)

    return None


# =============================================================================
# Contradiction Classifier Engine
# =============================================================================


class ContradictionClassifier:
    """Engine for classifying contradictions by type.

    Story 5-3: Third stage of the Contradiction Engine pipeline.

    Pipeline:
    1. STATEMENT QUERYING (5-1) -> 2. PAIR COMPARISON (5-2) ->
    3. CLASSIFICATION (5-3) -> 4. SEVERITY SCORING (5-4)

    Classification Strategy:
    - PREFER rule-based classification from EvidenceType (80%+ of cases)
    - Only use GPT-4 fallback for ambiguous cases (EvidenceType.NONE)
    - Cost: Rule-based = $0, LLM fallback ~$0.03 per call

    Example:
        >>> classifier = ContradictionClassifier()
        >>> result = await classifier.classify_contradiction(comparison)
        >>> result.classified_contradiction.contradiction_type
        ContradictionType.DATE_MISMATCH
    """

    def __init__(self) -> None:
        """Initialize contradiction classifier."""
        self._client = None
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_comparison_model

    @property
    def client(self):
        """Get or create OpenAI client (lazy initialization).

        Returns:
            OpenAI client instance.

        Raises:
            ClassifierError: If API key is not configured.
        """
        if self._client is None:
            if not self.api_key:
                raise ClassifierError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable.",
                    code="OPENAI_NOT_CONFIGURED",
                    is_retryable=False,
                )

            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info(
                    "contradiction_classifier_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("contradiction_classifier_init_failed", error=str(e))
                raise ClassifierError(
                    f"Failed to initialize OpenAI client: {e}",
                    code="CLIENT_INIT_FAILED",
                    is_retryable=False,
                ) from e

        return self._client

    async def classify_contradiction(
        self,
        comparison: StatementPairComparison,
    ) -> ClassificationResult:
        """Classify a single contradiction by type.

        Story 5-3: Main classification entry point.

        Args:
            comparison: StatementPairComparison with result=CONTRADICTION.

        Returns:
            ClassificationResult with classified contradiction and metadata.

        Raises:
            ClassifierError: If comparison is not a contradiction.
        """
        start_time = time.time()

        # Validate input
        if comparison.result != ComparisonResult.CONTRADICTION:
            raise ClassifierError(
                f"Cannot classify non-contradiction: {comparison.result.value}",
                code="INVALID_INPUT",
                is_retryable=False,
            )

        # Try rule-based classification first
        classification_result = self._classify_rule_based(comparison)

        if classification_result:
            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "contradiction_classified_rule_based",
                statement_a_id=comparison.statement_a_id,
                statement_b_id=comparison.statement_b_id,
                contradiction_type=classification_result.contradiction_type.value,
                processing_time_ms=processing_time,
            )

            return ClassificationResult(
                classified_contradiction=classification_result,
                llm_cost_usd=0.0,
                processing_time_ms=processing_time,
            )

        # Fall back to LLM classification
        logger.info(
            "contradiction_classification_llm_fallback",
            statement_a_id=comparison.statement_a_id,
            statement_b_id=comparison.statement_b_id,
            reason="evidence_type_none_or_ambiguous",
        )

        classification_result, cost_tracker = await self._classify_with_llm(comparison)
        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "contradiction_classified_llm",
            statement_a_id=comparison.statement_a_id,
            statement_b_id=comparison.statement_b_id,
            contradiction_type=classification_result.contradiction_type.value,
            cost_usd=cost_tracker.cost_usd,
            processing_time_ms=processing_time,
        )

        return ClassificationResult(
            classified_contradiction=classification_result,
            llm_cost_usd=cost_tracker.cost_usd,
            processing_time_ms=processing_time,
        )

    def _classify_rule_based(
        self,
        comparison: StatementPairComparison,
    ) -> ClassifiedContradiction | None:
        """Attempt rule-based classification using evidence type mapping.

        Story 5-3: 80%+ of classifications should succeed here.

        Args:
            comparison: Comparison with evidence type.

        Returns:
            ClassifiedContradiction if successfully classified, None otherwise.
        """
        evidence_type = comparison.evidence.type

        # Check if evidence type maps to contradiction type
        if evidence_type == EvidenceType.NONE:
            # Cannot classify with rule-based approach
            return None

        # Direct mapping
        contradiction_type = CLASSIFICATION_MAP.get(evidence_type)
        if not contradiction_type:
            # Unknown evidence type, need LLM
            return None

        # Create extracted values for attorney display
        extracted_values = create_extracted_values(
            evidence_type=evidence_type,
            value_a=comparison.evidence.value_a,
            value_b=comparison.evidence.value_b,
        )

        # Generate explanation from reasoning
        explanation = self._generate_explanation(
            contradiction_type=contradiction_type,
            reasoning=comparison.reasoning,
            value_a=comparison.evidence.value_a,
            value_b=comparison.evidence.value_b,
        )

        return ClassifiedContradiction(
            comparison_id=f"{comparison.statement_a_id}_{comparison.statement_b_id}",
            statement_a_id=comparison.statement_a_id,
            statement_b_id=comparison.statement_b_id,
            contradiction_type=contradiction_type,
            extracted_values=extracted_values,
            explanation=explanation,
            classification_method="rule_based",
        )

    def _generate_explanation(
        self,
        contradiction_type: ContradictionType,
        reasoning: str,
        value_a: str | None,
        value_b: str | None,
    ) -> str:
        """Generate attorney-friendly explanation from comparison reasoning.

        Args:
            contradiction_type: The classified type.
            reasoning: Original reasoning from GPT-4 comparison (truncated if >500 chars).
            value_a: Extracted value from statement A.
            value_b: Extracted value from statement B.

        Returns:
            Clear explanation string (max ~700 chars for readability).
        """
        # Truncate reasoning to prevent overly long explanations
        max_reasoning_length = 500
        truncated_reasoning = reasoning
        if len(reasoning) > max_reasoning_length:
            truncated_reasoning = reasoning[:max_reasoning_length] + "..."

        match contradiction_type:
            case ContradictionType.DATE_MISMATCH:
                if value_a and value_b:
                    return f"Statements conflict on dates: '{value_a}' vs '{value_b}'. {truncated_reasoning}"
                return f"Date conflict detected. {truncated_reasoning}"

            case ContradictionType.AMOUNT_MISMATCH:
                if value_a and value_b:
                    return f"Statements conflict on amounts: '{value_a}' vs '{value_b}'. {truncated_reasoning}"
                return f"Amount conflict detected. {truncated_reasoning}"

            case ContradictionType.FACTUAL_CONTRADICTION:
                return f"Direct factual conflict detected. {truncated_reasoning}"

            case ContradictionType.SEMANTIC_CONTRADICTION:
                return f"Semantic conflict - statements have opposing meanings. {truncated_reasoning}"

            case _:
                # Default case for future ContradictionType additions
                return f"Conflict detected. {truncated_reasoning}"

    async def _classify_with_llm(
        self,
        comparison: StatementPairComparison,
    ) -> tuple[ClassifiedContradiction, ClassificationCostTracker]:
        """Classify contradiction using GPT-4 fallback.

        Story 5-3: Used only when rule-based fails (~20% of cases).

        Args:
            comparison: Comparison requiring LLM analysis.

        Returns:
            Tuple of (ClassifiedContradiction, cost tracker).
        """
        cost_tracker = ClassificationCostTracker(used_llm=True)

        user_prompt = format_classification_prompt(
            content_a=comparison.statement_a_content,
            content_b=comparison.statement_b_content,
            reasoning=comparison.reasoning,
        )

        # Retry with exponential backoff
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": CLASSIFICATION_ENHANCEMENT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )

                # Track tokens
                cost_tracker.input_tokens = response.usage.prompt_tokens if response.usage else 0
                cost_tracker.output_tokens = response.usage.completion_tokens if response.usage else 0

                # Parse response
                response_text = response.choices[0].message.content
                parsed = json.loads(response_text)

                # Validate response
                validation_errors = validate_classification_response(parsed)
                if validation_errors:
                    logger.warning(
                        "classification_response_validation_failed",
                        errors=validation_errors,
                    )

                # Parse classification type
                type_str = parsed.get("contradiction_type", "semantic_contradiction").lower()
                contradiction_type = ContradictionType(type_str)

                # Extract values if they exist in evidence
                extracted_values = create_extracted_values(
                    evidence_type=comparison.evidence.type,
                    value_a=comparison.evidence.value_a,
                    value_b=comparison.evidence.value_b,
                )

                classified = ClassifiedContradiction(
                    comparison_id=f"{comparison.statement_a_id}_{comparison.statement_b_id}",
                    statement_a_id=comparison.statement_a_id,
                    statement_b_id=comparison.statement_b_id,
                    contradiction_type=contradiction_type,
                    extracted_values=extracted_values,
                    explanation=parsed.get("explanation", comparison.reasoning),
                    classification_method="llm_fallback",
                )

                return classified, cost_tracker

            except json.JSONDecodeError as e:
                last_error = ClassificationParseError(f"Invalid JSON: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_retryable = (
                    "429" in error_str
                    or "rate" in error_str
                    or "500" in error_str
                    or "502" in error_str
                    or "503" in error_str
                    or "504" in error_str
                    or "timeout" in error_str
                )

                if is_retryable and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "classification_llm_retrying",
                        attempt=attempt + 1,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_retryable:
                    break

        # Failed after all retries - fall back to semantic classification
        logger.error(
            "classification_llm_failed",
            error=str(last_error),
            fallback="semantic_contradiction",
        )

        # Return best-effort classification
        return ClassifiedContradiction(
            comparison_id=f"{comparison.statement_a_id}_{comparison.statement_b_id}",
            statement_a_id=comparison.statement_a_id,
            statement_b_id=comparison.statement_b_id,
            contradiction_type=ContradictionType.SEMANTIC_CONTRADICTION,
            extracted_values=None,
            explanation=f"Classification fallback due to LLM error. Original reasoning: {comparison.reasoning}",
            classification_method="llm_fallback_error",
        ), cost_tracker

    async def classify_all(
        self,
        comparisons: list[StatementPairComparison],
    ) -> list[ClassificationResult]:
        """Classify all contradictions in a batch.

        Args:
            comparisons: List of comparisons (filters to contradictions only).

        Returns:
            List of ClassificationResults for contradictions only.
        """
        # Filter to contradictions only
        contradictions = [
            c for c in comparisons
            if c.result == ComparisonResult.CONTRADICTION
        ]

        if not contradictions:
            return []

        # Classify each (mostly rule-based, very fast)
        results: list[ClassificationResult] = []
        for comparison in contradictions:
            try:
                result = await self.classify_contradiction(comparison)
                results.append(result)
            except ClassifierError as e:
                logger.warning(
                    "classification_failed",
                    statement_a_id=comparison.statement_a_id,
                    statement_b_id=comparison.statement_b_id,
                    error=str(e),
                )

        return results


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_contradiction_classifier() -> ContradictionClassifier:
    """Get singleton contradiction classifier instance.

    Returns:
        ContradictionClassifier instance.
    """
    return ContradictionClassifier()
