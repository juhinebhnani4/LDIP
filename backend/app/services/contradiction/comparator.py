"""Statement Comparison Service for contradiction detection.

Story 5-2: Service layer that wraps the StatementComparator engine
and provides a clean interface for API routes.

CRITICAL: Validates matter_id on every request (Layer 4 isolation).
"""

from functools import lru_cache

import structlog

from app.engines.contradiction import (
    StatementComparator,
    get_statement_comparator,
)
from app.models.contradiction import (
    ComparisonMeta,
    ComparisonResult,
    EntityComparisons,
    EntityComparisonsResponse,
)
from app.services.contradiction.statement_query import (
    EntityNotFoundError,
    StatementQueryService,
    get_statement_query_service,
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

            # Get all statements for entity using pagination to avoid OOM
            # The response structure is: EntityStatements.documents[].statements[]
            all_documents_data: dict[str, list] = {}  # doc_id -> statements
            stmt_page = 1
            batch_size = 200

            while True:
                statement_response = await self.statement_service.get_entity_statements(
                    entity_id=entity_id,
                    matter_id=matter_id,
                    include_aliases=include_aliases,
                    page=stmt_page,
                    per_page=batch_size,
                )

                # Collect statements from each document
                for doc in statement_response.data.documents:
                    if doc.document_id not in all_documents_data:
                        all_documents_data[doc.document_id] = []
                    all_documents_data[doc.document_id].extend(doc.statements)

                # Count total statements loaded
                total_loaded = sum(len(stmts) for stmts in all_documents_data.values())

                # Check if we've loaded all
                if total_loaded >= statement_response.data.total_statements:
                    break
                if not statement_response.data.documents:
                    break
                stmt_page += 1

            # Use the last response as base and it already has the correct structure
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

    async def compare_statements_by_canonical_name(
        self,
        canonical_name: str,
        matter_id: str,
        max_pairs: int = DEFAULT_MAX_PAIRS,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> EntityComparisonsResponse:
        """Compare statements across ALL entity_ids with the same canonical_name.

        This method enables cross-type comparison: if "Custodian" exists as both
        PERSON and ORGANIZATION types, their statements will be compared together.

        Story 5-2 enhancement: Group entities by name, ignoring type, for broader
        contradiction detection coverage.

        Args:
            canonical_name: Entity canonical name to match.
            matter_id: Matter UUID for isolation (CRITICAL).
            max_pairs: Maximum pairs to compare (cost control).
            confidence_threshold: Minimum confidence to include.

        Returns:
            EntityComparisonsResponse with comparisons across all matching entities.
        """
        from app.services.supabase.client import get_supabase_client

        logger.info(
            "compare_statements_by_canonical_name_request",
            canonical_name=canonical_name,
            matter_id=matter_id,
            max_pairs=max_pairs,
        )

        client = get_supabase_client()

        # Get ALL entity_ids with this canonical_name in the matter (ignoring type)
        entities_resp = (
            client.table("identity_nodes")
            .select("id, canonical_name, entity_type")
            .eq("matter_id", matter_id)
            .eq("canonical_name", canonical_name)
            .execute()
        )

        entity_ids = [e["id"] for e in (entities_resp.data or [])]

        if not entity_ids:
            logger.warning(
                "compare_by_name_no_entities_found",
                canonical_name=canonical_name,
                matter_id=matter_id,
            )
            return self._create_empty_response(
                entity_id="",
                entity_name=canonical_name,
            )

        # Log if multiple types found (the whole point of this method)
        entity_types = [e.get("entity_type") for e in (entities_resp.data or [])]
        if len(set(entity_types)) > 1:
            logger.info(
                "compare_by_name_cross_type_match",
                canonical_name=canonical_name,
                entity_types=list(set(entity_types)),
                entity_count=len(entity_ids),
            )

        # Use the first entity_id as the "primary" for response structure
        primary_entity_id = entity_ids[0]

        # Get statements for ALL entity_ids using overlaps query
        return await self._compare_merged_entity_statements(
            entity_ids=entity_ids,
            entity_name=canonical_name,
            matter_id=matter_id,
            max_pairs=max_pairs,
            confidence_threshold=confidence_threshold,
            primary_entity_id=primary_entity_id,
        )

    async def _compare_merged_entity_statements(
        self,
        entity_ids: list[str],
        entity_name: str,
        matter_id: str,
        max_pairs: int,
        confidence_threshold: float,
        primary_entity_id: str,
    ) -> EntityComparisonsResponse:
        """Compare statements that mention ANY of the given entity_ids.

        This enables cross-type comparison by merging statements from
        multiple entity_ids with the same canonical_name.

        Args:
            entity_ids: List of entity UUIDs to search for.
            entity_name: Display name for the entity group.
            matter_id: Matter UUID for isolation.
            max_pairs: Maximum pairs to compare.
            confidence_threshold: Minimum confidence threshold.
            primary_entity_id: ID to use for response structure.

        Returns:
            EntityComparisonsResponse with merged statement comparisons.
        """
        from app.models.contradiction import (
            DocumentStatements,
            EntityStatements,
            Statement,
        )
        from app.services.supabase.client import get_supabase_client

        client = get_supabase_client()

        # Query chunks containing ANY of the entity_ids
        chunks_resp = (
            client.table("chunks")
            .select("id, document_id, content, page_number, bbox_ids, entity_ids")
            .eq("matter_id", matter_id)
            .overlaps("entity_ids", entity_ids)
            .order("document_id")
            .order("page_number")
            .execute()
        )

        chunks = chunks_resp.data or []

        if len(chunks) < 2:
            logger.info(
                "compare_merged_insufficient_statements",
                entity_name=entity_name,
                chunk_count=len(chunks),
            )
            return self._create_empty_response(
                entity_id=primary_entity_id,
                entity_name=entity_name,
            )

        # Get document names
        doc_ids = list(set(c["document_id"] for c in chunks))
        docs_resp = (
            client.table("documents")
            .select("id, filename")
            .in_("id", doc_ids)
            .execute()
        )
        doc_names = {d["id"]: d.get("filename", "Unknown") for d in (docs_resp.data or [])}

        # Build EntityStatements structure from chunks
        # Group by document
        docs_map: dict[str, list[dict]] = {}
        for chunk in chunks:
            doc_id = chunk["document_id"]
            if doc_id not in docs_map:
                docs_map[doc_id] = []
            docs_map[doc_id].append(chunk)

        # Build document statements
        document_statements: list[DocumentStatements] = []
        from app.engines.contradiction.statement_query import ValueExtractor
        extractor = ValueExtractor()

        for doc_id, doc_chunks in docs_map.items():
            statements: list[Statement] = []
            for chunk in doc_chunks:
                content = chunk.get("content", "")
                dates, amounts = extractor.extract_all_values(content)
                statements.append(
                    Statement(
                        entity_id=primary_entity_id,
                        chunk_id=chunk.get("id", ""),
                        document_id=doc_id,
                        content=content,
                        dates=dates,
                        amounts=amounts,
                        page_number=chunk.get("page_number"),
                        bbox_ids=[str(b) for b in chunk.get("bbox_ids") or []],
                        confidence=1.0,
                    )
                )
            document_statements.append(
                DocumentStatements(
                    document_id=doc_id,
                    document_name=doc_names.get(doc_id),
                    statements=statements,
                    statement_count=len(statements),
                )
            )

        total_statements = sum(ds.statement_count for ds in document_statements)

        entity_statements = EntityStatements(
            entity_id=primary_entity_id,
            entity_name=entity_name,
            total_statements=total_statements,
            documents=document_statements,
            aliases_included=[],
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
            entity_id=primary_entity_id,
            entity_name=entity_name,
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
            "compare_merged_statements_success",
            entity_name=entity_name,
            entity_ids_count=len(entity_ids),
            pairs_compared=len(batch_result.comparisons),
            contradictions_found=batch_result.contradictions_found,
        )

        return EntityComparisonsResponse(
            data=entity_comparisons,
            meta=meta,
        )

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
