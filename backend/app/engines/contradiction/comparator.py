"""Statement Comparator Engine for pairwise contradiction detection.

Story 5-2: Statement Pair Comparison

Compares pairs of statements about the same entity using GPT-4 to detect
contradictions. Implements chain-of-thought reasoning for attorney review.

CRITICAL: Uses GPT-4 per LLM routing rules (ADR-002).
Contradiction detection = high-stakes reasoning, user-facing.
"""

import asyncio
import itertools
import json
import time
from dataclasses import dataclass, field
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.engines.contradiction.prompts import (
    COMPARISON_RESPONSE_SCHEMA,
    STATEMENT_COMPARISON_SYSTEM_PROMPT,
    format_comparison_prompt,
)
from app.models.contradiction import (
    ComparisonResult,
    ContradictionEvidence,
    EntityComparisons,
    EntityStatements,
    EvidenceType,
    Statement,
    StatementPairComparison,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# GPT-4 Turbo pricing (as of Jan 2025)
GPT4_INPUT_COST_PER_1K = 0.01  # $0.01 per 1K input tokens
GPT4_OUTPUT_COST_PER_1K = 0.03  # $0.03 per 1K output tokens

# Rate limiting
DEFAULT_BATCH_SIZE = 5  # Process 5 pairs in parallel (rate limit safe)
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0


# =============================================================================
# Cost Tracking
# =============================================================================


@dataclass
class LLMCostTracker:
    """Track LLM costs per comparison.

    Story 5-2: Cost control is critical for high-volume comparisons.
    """

    model: str = "gpt-4-turbo-preview"
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        """Calculate total cost in USD.

        Returns:
            Total cost based on token counts.
        """
        input_cost = (self.input_tokens / 1000) * GPT4_INPUT_COST_PER_1K
        output_cost = (self.output_tokens / 1000) * GPT4_OUTPUT_COST_PER_1K
        return input_cost + output_cost


@dataclass
class ComparisonBatchResult:
    """Result of comparing multiple statement pairs.

    Aggregates individual comparison results with cost tracking.
    """

    comparisons: list[StatementPairComparison] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    processing_time_ms: int = 0

    @property
    def total_cost_usd(self) -> float:
        """Calculate total cost for all comparisons."""
        input_cost = (self.total_input_tokens / 1000) * GPT4_INPUT_COST_PER_1K
        output_cost = (self.total_output_tokens / 1000) * GPT4_OUTPUT_COST_PER_1K
        return input_cost + output_cost

    @property
    def contradictions_found(self) -> int:
        """Count contradictions in results."""
        return sum(
            1 for c in self.comparisons
            if c.result == ComparisonResult.CONTRADICTION
        )


# =============================================================================
# Exceptions
# =============================================================================


class ComparatorError(Exception):
    """Base exception for comparator operations."""

    def __init__(
        self,
        message: str,
        code: str = "COMPARATOR_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class OpenAIConfigurationError(ComparatorError):
    """Raised when OpenAI is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="OPENAI_NOT_CONFIGURED", is_retryable=False)


class ComparisonParseError(ComparatorError):
    """Raised when GPT-4 response cannot be parsed."""

    def __init__(self, message: str):
        super().__init__(message, code="PARSE_ERROR", is_retryable=True)


# =============================================================================
# Statement Pair
# =============================================================================


@dataclass
class StatementPair:
    """A pair of statements to compare.

    Story 5-2: Represents a unique pair for comparison.
    Pair order is normalized: (A,B) is same as (B,A).
    """

    statement_a: Statement
    statement_b: Statement
    entity_name: str
    doc_a_name: str | None = None
    doc_b_name: str | None = None

    @property
    def pair_key(self) -> tuple[str, str]:
        """Get normalized pair key for deduplication.

        Returns:
            Sorted tuple of chunk IDs.
        """
        ids = sorted([self.statement_a.chunk_id, self.statement_b.chunk_id])
        return (ids[0], ids[1])

    def is_cross_document(self) -> bool:
        """Check if statements are from different documents.

        Story 5-2: Only compare cross-document pairs per Dev Notes.
        """
        return self.statement_a.document_id != self.statement_b.document_id


# =============================================================================
# Statement Comparator Engine
# =============================================================================


class StatementComparator:
    """Engine for comparing statement pairs using GPT-4.

    Story 5-2: Implements the second stage of the Contradiction Engine pipeline.

    Pipeline:
    1. STATEMENT QUERYING (5-1) -> 2. PAIR COMPARISON (5-2) -> 3. CLASSIFICATION (5-3)

    CRITICAL: Uses GPT-4 for chain-of-thought reasoning per LLM routing rules.

    Example:
        >>> comparator = StatementComparator()
        >>> result = await comparator.compare_statement_pair(
        ...     statement_a=stmt_a,
        ...     statement_b=stmt_b,
        ...     entity_name="Nirav Jobalia",
        ... )
        >>> result.result
        ComparisonResult.CONTRADICTION
    """

    def __init__(self) -> None:
        """Initialize statement comparator."""
        self._client = None
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = "gpt-4-turbo-preview"  # Per Dev Notes

    @property
    def client(self):
        """Get or create OpenAI client.

        Returns:
            OpenAI client instance.

        Raises:
            OpenAIConfigurationError: If API key is not configured.
        """
        if self._client is None:
            if not self.api_key:
                raise OpenAIConfigurationError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
                )

            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info(
                    "statement_comparator_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("statement_comparator_init_failed", error=str(e))
                raise OpenAIConfigurationError(
                    f"Failed to initialize OpenAI client: {e}"
                ) from e

        return self._client

    async def compare_statement_pair(
        self,
        statement_a: Statement,
        statement_b: Statement,
        entity_name: str,
        doc_a_name: str | None = None,
        doc_b_name: str | None = None,
    ) -> tuple[StatementPairComparison, LLMCostTracker]:
        """Compare a single pair of statements using GPT-4.

        Args:
            statement_a: First statement.
            statement_b: Second statement.
            entity_name: Name of the entity.
            doc_a_name: Optional document name for statement A.
            doc_b_name: Optional document name for statement B.

        Returns:
            Tuple of (comparison result, cost tracker).

        Raises:
            ComparatorError: If comparison fails after retries.
        """
        start_time = time.time()

        # Format prompt
        user_prompt = format_comparison_prompt(
            entity_name=entity_name,
            content_a=statement_a.content,
            content_b=statement_b.content,
            doc_a=doc_a_name or "Document A",
            doc_b=doc_b_name or "Document B",
            page_a=statement_a.page_number,
            page_b=statement_b.page_number,
        )

        # Retry with exponential backoff
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": STATEMENT_COMPARISON_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,  # Low temperature for consistent analysis
                )

                # Track tokens
                cost_tracker = LLMCostTracker(
                    model=self.model_name,
                    input_tokens=response.usage.prompt_tokens if response.usage else 0,
                    output_tokens=response.usage.completion_tokens if response.usage else 0,
                )

                # Parse response
                response_text = response.choices[0].message.content
                comparison = self._parse_comparison_response(
                    response_text=response_text,
                    statement_a=statement_a,
                    statement_b=statement_b,
                )

                processing_time = int((time.time() - start_time) * 1000)

                logger.info(
                    "statement_comparison_complete",
                    entity_name=entity_name,
                    result=comparison.result.value,
                    confidence=comparison.confidence,
                    cost_usd=cost_tracker.cost_usd,
                    processing_time_ms=processing_time,
                    attempts=attempt + 1,
                )

                return comparison, cost_tracker

            except OpenAIConfigurationError:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors
                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "statement_comparison_rate_limited",
                        attempt=attempt + 1,
                        max_attempts=MAX_RETRIES,
                        retry_delay=retry_delay,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "statement_comparison_failed",
            error=str(last_error),
            entity_name=entity_name,
            attempts=MAX_RETRIES,
        )

        raise ComparatorError(
            f"Statement comparison failed after {MAX_RETRIES} attempts: {last_error}",
            code="COMPARISON_FAILED",
        )

    async def compare_all_entity_statements(
        self,
        entity_statements: EntityStatements,
        max_pairs: int = 50,
        batch_size: int = DEFAULT_BATCH_SIZE,
        cross_document_only: bool = True,
    ) -> ComparisonBatchResult:
        """Compare all statement pairs for an entity.

        Generates unique pairs from EntityStatements and compares them
        using GPT-4 with parallel processing.

        Args:
            entity_statements: All statements about the entity (from Story 5-1).
            max_pairs: Maximum number of pairs to compare (cost control).
            batch_size: Number of parallel GPT-4 calls.
            cross_document_only: If True, only compare statements from different documents.

        Returns:
            ComparisonBatchResult with all comparisons and cost tracking.
        """
        start_time = time.time()

        # Generate unique pairs
        pairs = self._generate_statement_pairs(
            entity_statements=entity_statements,
            max_pairs=max_pairs,
            cross_document_only=cross_document_only,
        )

        if not pairs:
            logger.info(
                "no_pairs_to_compare",
                entity_id=entity_statements.entity_id,
                total_statements=entity_statements.total_statements,
            )
            return ComparisonBatchResult()

        logger.info(
            "starting_entity_comparison",
            entity_id=entity_statements.entity_id,
            entity_name=entity_statements.entity_name,
            total_pairs=len(pairs),
            batch_size=batch_size,
        )

        # Process in batches
        all_comparisons: list[StatementPairComparison] = []
        total_input_tokens = 0
        total_output_tokens = 0

        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]

            # Process batch in parallel
            tasks = [
                self.compare_statement_pair(
                    statement_a=pair.statement_a,
                    statement_b=pair.statement_b,
                    entity_name=pair.entity_name,
                    doc_a_name=pair.doc_a_name,
                    doc_b_name=pair.doc_b_name,
                )
                for pair in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(
                        "pair_comparison_failed",
                        error=str(result),
                    )
                    continue

                comparison, cost_tracker = result
                all_comparisons.append(comparison)
                total_input_tokens += cost_tracker.input_tokens
                total_output_tokens += cost_tracker.output_tokens

        processing_time = int((time.time() - start_time) * 1000)

        result = ComparisonBatchResult(
            comparisons=all_comparisons,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            processing_time_ms=processing_time,
        )

        logger.info(
            "entity_comparison_complete",
            entity_id=entity_statements.entity_id,
            pairs_compared=len(all_comparisons),
            contradictions_found=result.contradictions_found,
            total_cost_usd=result.total_cost_usd,
            processing_time_ms=processing_time,
        )

        return result

    def _generate_statement_pairs(
        self,
        entity_statements: EntityStatements,
        max_pairs: int,
        cross_document_only: bool = True,
    ) -> list[StatementPair]:
        """Generate unique statement pairs for comparison.

        Story 5-2: Generates N*(N-1)/2 unique pairs, deduplicating (A,B) == (B,A).

        Args:
            entity_statements: All statements grouped by document.
            max_pairs: Maximum pairs to generate.
            cross_document_only: Only compare statements from different documents.

        Returns:
            List of StatementPair objects.
        """
        # Flatten all statements
        all_statements: list[tuple[Statement, str | None]] = []  # (statement, doc_name)
        for doc in entity_statements.documents:
            for stmt in doc.statements:
                all_statements.append((stmt, doc.document_name))

        if len(all_statements) < 2:
            return []

        # Generate unique pairs
        pairs: list[StatementPair] = []
        seen_keys: set[tuple[str, str]] = set()

        for (stmt_a, doc_a_name), (stmt_b, doc_b_name) in itertools.combinations(all_statements, 2):
            # Skip same-document pairs if cross_document_only
            if cross_document_only and stmt_a.document_id == stmt_b.document_id:
                continue

            # Create pair
            pair = StatementPair(
                statement_a=stmt_a,
                statement_b=stmt_b,
                entity_name=entity_statements.entity_name,
                doc_a_name=doc_a_name,
                doc_b_name=doc_b_name,
            )

            # Deduplicate
            if pair.pair_key not in seen_keys:
                seen_keys.add(pair.pair_key)
                pairs.append(pair)

            # Stop at max_pairs
            if len(pairs) >= max_pairs:
                break

        logger.debug(
            "statement_pairs_generated",
            entity_id=entity_statements.entity_id,
            total_statements=len(all_statements),
            total_pairs=len(pairs),
            max_pairs=max_pairs,
            cross_document_only=cross_document_only,
        )

        return pairs

    def _parse_comparison_response(
        self,
        response_text: str,
        statement_a: Statement,
        statement_b: Statement,
    ) -> StatementPairComparison:
        """Parse GPT-4 response into StatementPairComparison.

        Args:
            response_text: Raw JSON response from GPT-4.
            statement_a: First statement.
            statement_b: Second statement.

        Returns:
            Parsed StatementPairComparison.

        Raises:
            ComparisonParseError: If response cannot be parsed.
        """
        try:
            parsed = json.loads(response_text)

            # Parse result enum
            result_str = parsed.get("result", "uncertain").lower()
            result = ComparisonResult(result_str)

            # Parse evidence
            evidence_data = parsed.get("evidence", {})
            evidence_type_str = evidence_data.get("type", "none").lower()
            evidence_type = EvidenceType(evidence_type_str)

            evidence = ContradictionEvidence(
                type=evidence_type,
                value_a=evidence_data.get("value_a"),
                value_b=evidence_data.get("value_b"),
                page_refs={
                    "statement_a": statement_a.page_number,
                    "statement_b": statement_b.page_number,
                },
            )

            return StatementPairComparison(
                statement_a_id=statement_a.chunk_id,
                statement_b_id=statement_b.chunk_id,
                statement_a_content=statement_a.content,
                statement_b_content=statement_b.content,
                result=result,
                reasoning=parsed.get("reasoning", ""),
                confidence=float(parsed.get("confidence", 0.5)),
                evidence=evidence,
                document_a_id=statement_a.document_id,
                document_b_id=statement_b.document_id,
                page_a=statement_a.page_number,
                page_b=statement_b.page_number,
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "comparison_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            raise ComparisonParseError(f"Invalid JSON response: {e}") from e

        except (KeyError, ValueError) as e:
            logger.warning(
                "comparison_response_parse_error",
                error=str(e),
            )
            raise ComparisonParseError(f"Failed to parse comparison: {e}") from e


# =============================================================================
# Service Factories
# =============================================================================


@lru_cache(maxsize=1)
def get_statement_comparator() -> StatementComparator:
    """Get singleton statement comparator instance.

    Returns:
        StatementComparator instance.
    """
    return StatementComparator()
