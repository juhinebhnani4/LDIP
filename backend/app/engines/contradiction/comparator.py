"""Statement Comparator Engine for pairwise contradiction detection.

Story 5-2: Statement Pair Comparison
Story 13-2: Circuit breaker protection for GPT-4 calls

Compares pairs of statements about the same entity using GPT-4 to detect
contradictions. Implements chain-of-thought reasoning for attorney review.

CRITICAL: Uses GPT-4 per LLM routing rules (ADR-002).
Contradiction detection = high-stakes reasoning, user-facing.

Fallback: Circuit open raises ComparatorError - no silent fallback for
high-stakes contradiction detection (user must be aware of degraded state).
"""

import asyncio
import itertools
import json
import time
from dataclasses import dataclass, field
from functools import lru_cache

import structlog

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings
from app.core.llm_rate_limiter import LLMProvider, get_rate_limiter
from app.engines.contradiction.prompts import (
    GEMINI_SCREENING_SYSTEM_PROMPT,
    STATEMENT_COMPARISON_SYSTEM_PROMPT,
    format_comparison_prompt,
    format_screening_prompt,
    validate_comparison_response,
    validate_screening_response,
)
from app.models.contradiction import (
    ComparisonResult,
    ContradictionEvidence,
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

# Gemini Flash pricing (as of Jan 2025) - much cheaper for screening
GEMINI_INPUT_COST_PER_1K = 0.000075  # $0.075 per 1M input tokens
GEMINI_OUTPUT_COST_PER_1K = 0.0003  # $0.30 per 1M output tokens

# Rate limiting
DEFAULT_BATCH_SIZE = 5  # Process 5 pairs in parallel (rate limit safe)


# =============================================================================
# Cost Tracking
# =============================================================================


@dataclass
class LLMCostTracker:
    """Track LLM costs per comparison.

    Story 5-2: Cost control is critical for high-volume comparisons.
    Supports both GPT-4 (full analysis) and Gemini (screening) costs.
    """

    model: str = "gpt-4-turbo-preview"
    input_tokens: int = 0
    output_tokens: int = 0
    # Two-tier routing tracking
    screening_model: str | None = None
    screening_input_tokens: int = 0
    screening_output_tokens: int = 0
    was_escalated: bool = False  # True if escalated to GPT-4

    @property
    def cost_usd(self) -> float:
        """Calculate total cost in USD.

        Returns:
            Total cost based on token counts for both tiers.
        """
        total_cost = 0.0

        # Screening tier cost (Gemini)
        if self.screening_model:
            screening_input = (self.screening_input_tokens / 1000) * GEMINI_INPUT_COST_PER_1K
            screening_output = (self.screening_output_tokens / 1000) * GEMINI_OUTPUT_COST_PER_1K
            total_cost += screening_input + screening_output

        # Full analysis tier cost (GPT-4) - only if escalated
        if self.input_tokens > 0 or self.output_tokens > 0:
            input_cost = (self.input_tokens / 1000) * GPT4_INPUT_COST_PER_1K
            output_cost = (self.output_tokens / 1000) * GPT4_OUTPUT_COST_PER_1K
            total_cost += input_cost + output_cost

        return total_cost


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
    """Engine for comparing statement pairs using two-tier model routing.

    Story 5-2: Implements the second stage of the Contradiction Engine pipeline.

    Pipeline:
    1. STATEMENT QUERYING (5-1) -> 2. PAIR COMPARISON (5-2) -> 3. CLASSIFICATION (5-3)

    Cost Optimization (Two-Tier Routing):
    - Tier 1: Gemini Flash for quick screening (~$0.0001/comparison)
    - Tier 2: GPT-4 for uncertain/contradiction results (~$0.025/comparison)
    - Expected cost reduction: 60-80% for typical legal document analysis

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
        """Initialize statement comparator with two-tier model routing."""
        self._openai_client = None
        self._gemini_model = None
        settings = get_settings()

        # OpenAI (GPT-4) config
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_comparison_model

        # Two-tier routing config
        self.routing_enabled = settings.contradiction_model_routing_enabled
        self.screening_model = settings.contradiction_screening_model
        self.confidence_threshold = settings.contradiction_screening_confidence_threshold
        self.escalate_results = settings.contradiction_escalate_results

        # Gemini API key (reuse from entity extraction)
        self.gemini_api_key = settings.gemini_api_key

    @property
    def client(self):
        """Get or create OpenAI client.

        Returns:
            OpenAI client instance.

        Raises:
            OpenAIConfigurationError: If API key is not configured.
        """
        if self._openai_client is None:
            if not self.api_key:
                raise OpenAIConfigurationError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
                )

            try:
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(api_key=self.api_key)
                logger.info(
                    "statement_comparator_initialized",
                    model=self.model_name,
                    routing_enabled=self.routing_enabled,
                )
            except Exception as e:
                logger.error("statement_comparator_init_failed", error=str(e))
                raise OpenAIConfigurationError(
                    f"Failed to initialize OpenAI client: {e}"
                ) from e

        return self._openai_client

    @property
    def gemini_model(self):
        """Get or create Gemini model for screening.

        Returns:
            Gemini GenerativeModel instance.

        Raises:
            ComparatorError: If Gemini API key is not configured.
        """
        if self._gemini_model is None:
            if not self.gemini_api_key:
                logger.warning(
                    "gemini_not_configured_for_screening",
                    hint="Set GEMINI_API_KEY for two-tier routing cost savings",
                )
                return None

            try:
                import google.generativeai as genai

                genai.configure(api_key=self.gemini_api_key)
                self._gemini_model = genai.GenerativeModel(self.screening_model)
                logger.info(
                    "gemini_screening_initialized",
                    model=self.screening_model,
                )
            except Exception as e:
                logger.error("gemini_screening_init_failed", error=str(e))
                return None

        return self._gemini_model

    async def compare_statement_pair(
        self,
        statement_a: Statement,
        statement_b: Statement,
        entity_name: str,
        doc_a_name: str | None = None,
        doc_b_name: str | None = None,
    ) -> tuple[StatementPairComparison, LLMCostTracker]:
        """Compare a single pair of statements using two-tier model routing.

        Two-tier routing (when enabled):
        1. Gemini Flash screens first (~$0.0001/comparison)
        2. GPT-4 only for uncertain/contradiction results (~$0.025/comparison)
        3. Consistent/unrelated results with high confidence skip GPT-4

        Args:
            statement_a: First statement.
            statement_b: Second statement.
            entity_name: Name of the entity.
            doc_a_name: Optional document name for statement A.
            doc_b_name: Optional document name for statement B.

        Returns:
            Tuple of (comparison result, cost tracker).

        Raises:
            ComparatorError: If comparison fails or circuit is open.
        """
        start_time = time.time()
        cost_tracker = LLMCostTracker(model=self.model_name)

        try:
            # === TIER 1: Gemini Screening (if enabled) ===
            if self.routing_enabled and self.gemini_model:
                screening_result = await self._call_gemini_screening(
                    entity_name=entity_name,
                    content_a=statement_a.content,
                    content_b=statement_b.content,
                )

                if screening_result:
                    result, confidence, quick_reason, in_tokens, out_tokens = screening_result

                    # Track screening costs
                    cost_tracker.screening_model = self.screening_model
                    cost_tracker.screening_input_tokens = in_tokens
                    cost_tracker.screening_output_tokens = out_tokens

                    # Check if we can skip GPT-4
                    skip_gpt4 = (
                        result in ("consistent", "unrelated")
                        and confidence >= self.confidence_threshold
                    )

                    if skip_gpt4:
                        # Use Gemini result directly - no GPT-4 needed
                        cost_tracker.was_escalated = False

                        # Map screening result to ComparisonResult
                        result_enum = (
                            ComparisonResult.CONSISTENT if result == "consistent"
                            else ComparisonResult.UNRELATED
                        )

                        comparison = StatementPairComparison(
                            statement_a_id=statement_a.chunk_id,
                            statement_b_id=statement_b.chunk_id,
                            statement_a_content=statement_a.content,
                            statement_b_content=statement_b.content,
                            result=result_enum,
                            reasoning=f"[Gemini screening] {quick_reason}",
                            confidence=confidence,
                            evidence=ContradictionEvidence(type=EvidenceType.NONE),
                            document_a_id=statement_a.document_id,
                            document_b_id=statement_b.document_id,
                            page_a=statement_a.page_number,
                            page_b=statement_b.page_number,
                        )

                        processing_time = int((time.time() - start_time) * 1000)
                        logger.info(
                            "statement_comparison_screened",
                            entity_name=entity_name,
                            result=comparison.result.value,
                            confidence=confidence,
                            cost_usd=cost_tracker.cost_usd,
                            processing_time_ms=processing_time,
                            escalated=False,
                        )
                        return comparison, cost_tracker

                    # Needs escalation to GPT-4
                    cost_tracker.was_escalated = True
                    logger.debug(
                        "screening_escalating_to_gpt4",
                        entity_name=entity_name,
                        screening_result=result,
                        screening_confidence=confidence,
                    )

            # === TIER 2: GPT-4 Full Analysis ===
            user_prompt = format_comparison_prompt(
                entity_name=entity_name,
                content_a=statement_a.content,
                content_b=statement_b.content,
                doc_a=doc_a_name or "Document A",
                doc_b=doc_b_name or "Document B",
                page_a=statement_a.page_number,
                page_b=statement_b.page_number,
            )

            response_text, input_tokens, output_tokens = await self._call_gpt4_comparison(
                user_prompt
            )

            # Track GPT-4 tokens
            cost_tracker.input_tokens = input_tokens
            cost_tracker.output_tokens = output_tokens

            # Parse response
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
                escalated=cost_tracker.was_escalated,
            )

            return comparison, cost_tracker

        except CircuitOpenError as e:
            # No silent fallback for high-stakes contradiction detection
            logger.error(
                "comparison_circuit_open",
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
                entity_name=entity_name,
            )
            raise ComparatorError(
                f"Contradiction analysis unavailable - GPT-4 circuit open. "
                f"Retry after {e.cooldown_remaining:.0f}s",
                code="CIRCUIT_OPEN",
                is_retryable=True,
            ) from e

        except OpenAIConfigurationError:
            raise

        except Exception as e:
            logger.error(
                "statement_comparison_failed",
                error=str(e),
                error_type=type(e).__name__,
                entity_name=entity_name,
            )
            raise ComparatorError(
                f"Statement comparison failed: {e}",
                code="COMPARISON_FAILED",
            ) from e

    async def _call_gemini_screening(
        self,
        entity_name: str,
        content_a: str,
        content_b: str,
    ) -> tuple[str, float, str, int, int] | None:
        """Call Gemini for fast screening with rate limiting.

        Args:
            entity_name: Name of the entity being discussed.
            content_a: Content of statement A.
            content_b: Content of statement B.

        Returns:
            Tuple of (result, confidence, quick_reason, input_tokens, output_tokens)
            or None if screening fails (will fall back to GPT-4).
        """
        try:
            screening_prompt = format_screening_prompt(
                entity_name=entity_name,
                content_a=content_a,
                content_b=content_b,
            )

            # Combine system + user prompt for Gemini
            full_prompt = f"{GEMINI_SCREENING_SYSTEM_PROMPT}\n\n{screening_prompt}"

            # Apply rate limiting to prevent 429 errors
            gemini_limiter = get_rate_limiter(LLMProvider.GEMINI)
            async with gemini_limiter:
                response = await asyncio.to_thread(
                    self.gemini_model.generate_content,
                    full_prompt,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    },
                )

            response_text = response.text

            # Parse JSON response
            parsed = json.loads(response_text)

            # Validate response
            validation_errors = validate_screening_response(parsed)
            if validation_errors:
                logger.warning(
                    "screening_validation_failed",
                    errors=validation_errors,
                )
                return None

            result = parsed.get("result", "needs_review").lower()
            confidence = float(parsed.get("confidence", 0.0))
            quick_reason = parsed.get("quick_reason", "")

            # Estimate tokens (Gemini doesn't always provide exact counts)
            input_tokens = len(full_prompt) // 4  # Rough estimate
            output_tokens = len(response_text) // 4

            return result, confidence, quick_reason, input_tokens, output_tokens

        except Exception as e:
            logger.warning(
                "gemini_screening_failed",
                error=str(e),
                hint="Falling back to GPT-4",
            )
            return None

    @with_circuit_breaker(CircuitService.OPENAI_CHAT)
    async def _call_gpt4_comparison(
        self, user_prompt: str
    ) -> tuple[str, int, int]:
        """Call GPT-4 API with circuit breaker protection.

        OpenAI Prompt Caching: Automatic caching applies when:
        - Total prompt >= 1024 tokens (system + user)
        - System prompt is identical across requests (which it is)
        - Requests within ~1 hour window
        Expected cache hit rate: ~50-70% for batch comparisons

        Args:
            user_prompt: Formatted user prompt.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens).
        """
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                # System prompt first - enables OpenAI's automatic prompt caching
                # When the same system prompt is used repeatedly, OpenAI caches it
                # and charges 50% less for cached input tokens
                {"role": "system", "content": STATEMENT_COMPARISON_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for consistent analysis
        )

        response_text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return response_text, input_tokens, output_tokens

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
        Applies pre-filtering optimization to prioritize suspicious pairs.

        Args:
            entity_statements: All statements grouped by document.
            max_pairs: Maximum pairs to generate.
            cross_document_only: Only compare statements from different documents.

        Returns:
            List of StatementPair objects, sorted by suspiciousness score.
        """
        # Flatten all statements
        all_statements: list[tuple[Statement, str | None]] = []  # (statement, doc_name)
        for doc in entity_statements.documents:
            for stmt in doc.statements:
                all_statements.append((stmt, doc.document_name))

        if len(all_statements) < 2:
            return []

        # Generate unique pairs with suspiciousness scores
        scored_pairs: list[tuple[float, StatementPair]] = []  # (score, pair)
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
            if pair.pair_key in seen_keys:
                continue
            seen_keys.add(pair.pair_key)

            # Pre-filter optimization: Calculate suspiciousness score
            # Pairs with conflicting extracted values are more likely contradictions
            suspiciousness = self._calculate_suspiciousness(stmt_a, stmt_b)
            scored_pairs.append((suspiciousness, pair))

        # Sort by suspiciousness (highest first) to prioritize likely contradictions
        scored_pairs.sort(key=lambda x: x[0], reverse=True)

        # Take top max_pairs
        pairs = [pair for _, pair in scored_pairs[:max_pairs]]

        logger.debug(
            "statement_pairs_generated",
            entity_id=entity_statements.entity_id,
            total_statements=len(all_statements),
            total_candidate_pairs=len(scored_pairs),
            selected_pairs=len(pairs),
            max_pairs=max_pairs,
            cross_document_only=cross_document_only,
        )

        return pairs

    def _calculate_suspiciousness(
        self,
        stmt_a: Statement,
        stmt_b: Statement,
    ) -> float:
        """Calculate suspiciousness score for a statement pair.

        Pre-filtering optimization: Pairs with conflicting extracted values
        are more likely to be contradictions and should be compared first.

        Args:
            stmt_a: First statement.
            stmt_b: Second statement.

        Returns:
            Suspiciousness score (0.0 - 1.0). Higher = more suspicious.
        """
        score = 0.0

        # Check for date conflicts
        if stmt_a.dates and stmt_b.dates:
            dates_a = {d.normalized for d in stmt_a.dates}
            dates_b = {d.normalized for d in stmt_b.dates}
            # Different dates = suspicious
            if dates_a and dates_b and dates_a != dates_b:
                score += 0.4

        # Check for amount conflicts
        if stmt_a.amounts and stmt_b.amounts:
            amounts_a = {a.normalized for a in stmt_a.amounts}
            amounts_b = {b.normalized for b in stmt_b.amounts}
            # Different amounts = very suspicious
            if amounts_a and amounts_b and amounts_a != amounts_b:
                score += 0.5

        # Boost if both have extracted values (more comparable)
        if (stmt_a.dates or stmt_a.amounts) and (stmt_b.dates or stmt_b.amounts):
            score += 0.1

        return min(score, 1.0)

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

            # Validate against schema
            validation_errors = validate_comparison_response(parsed)
            if validation_errors:
                logger.warning(
                    "comparison_response_validation_failed",
                    errors=validation_errors,
                    response_preview=response_text[:200] if response_text else "",
                )
                # Continue parsing with defaults for missing/invalid fields
                # This allows graceful degradation instead of hard failure

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
