"""Statement Query Service for entity-grouped statement retrieval.

Story 5-1: Service layer that wraps the StatementQueryEngine
and provides a clean interface for API routes.

CRITICAL: Validates matter_id on every request (Layer 4 isolation).
"""

import asyncio
from functools import lru_cache
from math import ceil

import structlog

from app.engines.contradiction import StatementQueryEngine, get_statement_query_engine
from app.models.contradiction import (
    EntityStatements,
    EntityStatementsResponse,
    PaginationMeta,
)
from app.services.mig.graph import MIGGraphService, get_mig_graph_service

logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class StatementQueryError(Exception):
    """Base exception for statement query operations."""

    def __init__(
        self,
        message: str,
        code: str = "STATEMENT_QUERY_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


class EntityNotFoundError(StatementQueryError):
    """Raised when entity is not found in matter."""

    def __init__(self, entity_id: str, matter_id: str):
        super().__init__(
            f"Entity {entity_id} not found in matter {matter_id}",
            code="ENTITY_NOT_FOUND",
        )
        self.entity_id = entity_id
        self.matter_id = matter_id


# =============================================================================
# Service Implementation
# =============================================================================


class StatementQueryService:
    """Service for querying entity-grouped statements.

    Provides:
    - Entity validation with matter isolation
    - Paginated statement retrieval
    - Alias resolution via MIG

    CRITICAL: Always validates that entity belongs to matter (Layer 4).

    Example:
        >>> service = StatementQueryService()
        >>> response = await service.get_entity_statements(
        ...     entity_id="entity-123",
        ...     matter_id="matter-456",
        ...     include_aliases=True,
        ... )
    """

    def __init__(self) -> None:
        """Initialize statement query service."""
        self._engine: StatementQueryEngine | None = None
        self._mig_service: MIGGraphService | None = None

    @property
    def engine(self) -> StatementQueryEngine:
        """Get statement query engine instance."""
        if self._engine is None:
            self._engine = get_statement_query_engine()
        return self._engine

    @property
    def mig_service(self) -> MIGGraphService:
        """Get MIG service instance."""
        if self._mig_service is None:
            self._mig_service = get_mig_graph_service()
        return self._mig_service

    # =========================================================================
    # Public Methods
    # =========================================================================

    async def get_entity_statements(
        self,
        entity_id: str,
        matter_id: str,
        include_aliases: bool = True,
        document_ids: list[str] | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> EntityStatementsResponse:
        """Get all statements about an entity, grouped by document.

        Implements AC #1: Retrieves all chunks mentioning the entity
        and groups them by document source.

        Implements AC #2: When include_aliases=True, also retrieves
        statements mentioning any alias of the entity.

        Implements AC #4: Returns empty result (not error) when no
        statements exist.

        Args:
            entity_id: Entity UUID to query.
            matter_id: Matter UUID for isolation (CRITICAL).
            include_aliases: If True, include alias entity matches.
            document_ids: Optional filter by document IDs.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            EntityStatementsResponse with paginated grouped statements.

        Raises:
            EntityNotFoundError: If entity not found in matter.
            StatementQueryError: If query fails.
        """
        logger.info(
            "get_entity_statements_request",
            entity_id=entity_id,
            matter_id=matter_id,
            include_aliases=include_aliases,
            page=page,
            per_page=per_page,
        )

        # CRITICAL: Validate entity exists in this matter (Layer 4)
        entity = await self.mig_service.get_entity(entity_id, matter_id)
        if entity is None:
            logger.warning(
                "get_entity_statements_entity_not_found",
                entity_id=entity_id,
                matter_id=matter_id,
            )
            raise EntityNotFoundError(entity_id, matter_id)

        try:
            # Get total count for pagination
            total_count = await self.engine.count_statements_for_entity(
                entity_id=entity_id,
                matter_id=matter_id,
                include_aliases=include_aliases,
            )

            # Get statements
            if include_aliases:
                entity_statements = await self.engine.get_statements_for_canonical_entity(
                    entity_id=entity_id,
                    matter_id=matter_id,
                    include_aliases=True,
                    document_ids=document_ids,
                    page=page,
                    per_page=per_page,
                )
            else:
                entity_statements = await self.engine.get_statements_for_entity(
                    entity_id=entity_id,
                    matter_id=matter_id,
                    document_ids=document_ids,
                    page=page,
                    per_page=per_page,
                )

            # Calculate pagination
            total_pages = ceil(total_count / per_page) if total_count > 0 else 0

            logger.info(
                "get_entity_statements_success",
                entity_id=entity_id,
                matter_id=matter_id,
                total_statements=entity_statements.total_statements,
                document_count=len(entity_statements.documents),
                aliases_count=len(entity_statements.aliases_included),
            )

            return EntityStatementsResponse(
                data=entity_statements,
                meta=PaginationMeta(
                    total=total_count,
                    page=page,
                    per_page=per_page,
                    total_pages=total_pages,
                ),
            )

        except Exception as e:
            logger.error(
                "get_entity_statements_error",
                entity_id=entity_id,
                matter_id=matter_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise StatementQueryError(
                f"Failed to query statements: {e!s}",
                code="QUERY_FAILED",
            ) from e

    async def get_entity_statement_count(
        self,
        entity_id: str,
        matter_id: str,
        include_aliases: bool = True,
    ) -> int:
        """Get count of statements for an entity.

        Useful for checking if any statements exist before
        full query.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.
            include_aliases: If True, include alias matches.

        Returns:
            Total count of statements.

        Raises:
            EntityNotFoundError: If entity not found in matter.
        """
        # Validate entity exists
        entity = await self.mig_service.get_entity(entity_id, matter_id)
        if entity is None:
            raise EntityNotFoundError(entity_id, matter_id)

        return await self.engine.count_statements_for_entity(
            entity_id=entity_id,
            matter_id=matter_id,
            include_aliases=include_aliases,
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_statement_query_service() -> StatementQueryService:
    """Get singleton statement query service instance.

    Returns:
        StatementQueryService instance.
    """
    return StatementQueryService()
