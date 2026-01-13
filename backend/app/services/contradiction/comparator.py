"""Statement Comparison Service for contradiction detection.

Story 5-2: Service layer that wraps the StatementComparator engine
and provides a clean interface for API routes.

CRITICAL: Validates matter_id on every request (Layer 4 isolation).
"""

import asyncio
from functools import lru_cache
from math import ceil

import structlog

from app.engines.contradiction import (
    ComparisonBatchResult,
    StatementComparator,
    get_statement_comparator,
)
from app.models.contradiction import (
    ComparisonMeta,
    ComparisonResult,
    EntityComparisons,
    EntityComparisonsResponse,
    EntityStatements,
)
from app.services.contradiction.statement_query import (
    StatementQueryService,
    get_statement_query_service,
    EntityNotFoundError,
    StatementQueryError,
)
from app.services.mig.graph import MIGGraphService, get_mig_graph_service

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default limits for cost control
DEFAULT_MAX_PAIRS = 50
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
ASYNC_THRESHOLD = 100  # If >100 statements, use async processing


# =============================================================================
# Exceptions
# =============================================================================


class ComparisonServiceError(Exception):
    """Base exception for comparison service operations."""

    def __init__(
        self,
        message: str,
        code: str = "COMPARISON_SERVICE_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


class TooManyStatementsError(ComparisonServiceError):
    """Raised when statement count exceeds async threshold."""

    def __init__(self, statement_count: int, threshold: int = ASYNC_THRESHOLD):
        super().__init__(
            f"Entity has {statement_count} statements, exceeding threshold of {threshold}. "
            "Use async processing instead.",
            code="TOO_MANY_STATEMENTS",
        )
        self.statement_count = statement_count
        self.threshold = threshold


# =============================================================================
# Service Implementation
# =============================================================================


class StatementComparisonService:
    """Service for comparing entity statements for contradictions.

    Provides:
    - Entity validation with matter isolation
    - Statement retrieval and comparison orchestration
    - Cost tracking and result aggregation

    CRITICAL: Always validates that entity belongs to matter (Layer 4).

    Example:
        >>> service = StatementComparisonService()
        >>> response = await service.compare_entity_statements(
        ...     entity_id="entity-123",
        ...     matter_id="matter-456",
        ...     max_pairs=50,
        ... )
        >>> response.meta.contradictions_found
        3
    """

    def __init__(self) -> None:
        """Initialize statement comparison service."""
        self._comparator: StatementComparator | None = None
        self._statement_service: StatementQueryService | None = None
        self._mig_service: MIGGraphService | None = None

    @property
    def comparator(self) -> StatementComparator:
        """Get statement comparator engine instance."""
        if self._comparator is None:
            self._comparator = get_statement_comparator()
        return self._comparator

    @property
    def statement_service(self) -> StatementQueryService:
        """Get statement query service instance."""
        if self._statement_service is None:
            self._statement_service = get_statement_query_service()
        return self._statement_service

    @property
    def mig_service(self) -> MIGGraphService:
        """Get MIG service instance."""
        if self._mig_service is None:
            self._mig_service = get_mig_graph_service()
        return self._mig_service

    # =========================================================================
    # Public Methods
    # =========================================================================

    async def compare_entity_statements(
        self,
        entity_id: str,
        matter_id: str,
        max_pairs: int = DEFAULT_MAX_PAIRS,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        include_aliases: bool = True,
    ) -> EntityComparisonsResponse:
        """Compare all statements about an entity for contradictions.

        Story 5-2: Main entry point for statement comparison.

        Implements:
        - AC #1: Compare each unique pair of statements
        - AC #2: Detect amount/date mismatches
        - AC #3: Mark consistent pairs as "consistent"
        - AC #4: Record chain-of-thought reasoning

        Args:
            entity_id: Entity UUID to compare statements for.
            matter_id: Matter UUID for isolation (CRITICAL).
            max_pairs: Maximum pairs to compare (cost control).
            confidence_threshold: Minimum confidence to include.
            include_aliases: Include statements from entity aliases.

        Returns:
            EntityComparisonsResponse with comparisons and cost metadata.

        Raises:
            EntityNotFoundError: If entity not found in matter.
            TooManyStatementsError: If >100 statements (use async).
            ComparisonServiceError: If comparison fails.
        """
        logger.info(
            "compare_entity_statements_request",
            entity_id=entity_id,
            matter_id=matter_id,
            max_pairs=max_pairs,
            confidence_threshold=confidence_threshold,
            include_aliases=include_aliases,
        )

        # CRITICAL: Validate entity exists in this matter (Layer 4)
        entity = await self.mig_service.get_entity(entity_id, matter_id)
        if entity is None:
            logger.warning(
                "compare_entity_statements_entity_not_found",
                entity_id=entity_id,
                matter_id=matter_id,
            )
            raise EntityNotFoundError(entity_id, matter_id)

        try:
            # Get statement count first for async threshold check
            statement_count = await self.statement_service.get_entity_statement_count(
                entity_id=entity_id,
                matter_id=matter_id,
                include_aliases=include_aliases,
            )

            # Check async threshold
            if statement_count > ASYNC_THRESHOLD:
                raise TooManyStatementsError(statement_count, ASYNC_THRESHOLD)

            # Get all statements for entity
            statement_response = await self.statement_service.get_entity_statements(
                entity_id=entity_id,
                matter_id=matter_id,
                include_aliases=include_aliases,
                page=1,
                per_page=1000,  # Get all for comparison
            )

            entity_statements = statement_response.data

            # Handle empty/single statement case
            if entity_statements.total_statements < 2:
                logger.info(
                    "compare_entity_statements_insufficient",
                    entity_id=entity_id,
                    total_statements=entity_statements.total_statements,
                )
                return self._create_empty_response(
                    entity_id=entity_id,
                    entity_name=entity_statements.entity_name,
                )

            # Run comparisons
            batch_result = await self.comparator.compare_all_entity_statements(
                entity_statements=entity_statements,
                max_pairs=max_pairs,
            )

            # Filter by confidence threshold
            filtered_comparisons = [
                c for c in batch_result.comparisons
                if c.confidence >= confidence_threshold
            ]

            # Build response
            entity_comparisons = EntityComparisons(
                entity_id=entity_id,
                entity_name=entity_statements.entity_name,
                comparisons=filtered_comparisons,
                contradictions_found=sum(
                    1 for c in filtered_comparisons
                    if c.result == ComparisonResult.CONTRADICTION
                ),
                total_pairs_compared=len(filtered_comparisons),
            )

            meta = ComparisonMeta(
                pairs_compared=len(batch_result.comparisons),
                contradictions_found=batch_result.contradictions_found,
                total_cost_usd=batch_result.total_cost_usd,
                processing_time_ms=batch_result.processing_time_ms,
            )

            logger.info(
                "compare_entity_statements_success",
                entity_id=entity_id,
                matter_id=matter_id,
                pairs_compared=len(batch_result.comparisons),
                contradictions_found=batch_result.contradictions_found,
                total_cost_usd=batch_result.total_cost_usd,
            )

            return EntityComparisonsResponse(
                data=entity_comparisons,
                meta=meta,
            )

        except (EntityNotFoundError, TooManyStatementsError):
            raise
        except Exception as e:
            logger.error(
                "compare_entity_statements_error",
                entity_id=entity_id,
                matter_id=matter_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ComparisonServiceError(
                f"Failed to compare statements: {e!s}",
                code="COMPARISON_FAILED",
            ) from e

    async def get_estimated_pairs(
        self,
        entity_id: str,
        matter_id: str,
        include_aliases: bool = True,
    ) -> int:
        """Estimate number of pairs for an entity.

        Useful for checking cost before running comparison.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.
            include_aliases: Include alias statements.

        Returns:
            Estimated number of unique pairs (N*(N-1)/2).
        """
        count = await self.statement_service.get_entity_statement_count(
            entity_id=entity_id,
            matter_id=matter_id,
            include_aliases=include_aliases,
        )

        # N*(N-1)/2 unique pairs
        return (count * (count - 1)) // 2

    def _create_empty_response(
        self,
        entity_id: str,
        entity_name: str,
    ) -> EntityComparisonsResponse:
        """Create empty response for insufficient statements."""
        return EntityComparisonsResponse(
            data=EntityComparisons(
                entity_id=entity_id,
                entity_name=entity_name,
                comparisons=[],
                contradictions_found=0,
                total_pairs_compared=0,
            ),
            meta=ComparisonMeta(
                pairs_compared=0,
                contradictions_found=0,
                total_cost_usd=0.0,
                processing_time_ms=0,
            ),
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_statement_comparison_service() -> StatementComparisonService:
    """Get singleton statement comparison service instance.

    Returns:
        StatementComparisonService instance.
    """
    return StatementComparisonService()
