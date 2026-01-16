"""Matter isolation tests for Contradiction API.

Story 5-1: Verify 4-layer matter isolation for statement querying.

CRITICAL: These tests ensure that the statement query service
correctly enforces matter isolation at Layer 4 (API middleware).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.contradiction import EntityStatements
from app.services.contradiction.statement_query import (
    EntityNotFoundError,
    StatementQueryService,
)


class TestContradictionMatterIsolation:
    """Tests for matter isolation in contradiction API.

    Verifies Layer 4 isolation: API validates entity belongs to matter.
    """

    @pytest.fixture
    def mock_mig_service(self) -> MagicMock:
        """Create mock MIG service."""
        return MagicMock()

    @pytest.fixture
    def mock_engine(self) -> MagicMock:
        """Create mock engine."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_mig_service: MagicMock, mock_engine: MagicMock) -> StatementQueryService:
        """Create service instance with mocked dependencies."""
        svc = StatementQueryService()
        svc._mig_service = mock_mig_service
        svc._engine = mock_engine
        return svc

    @pytest.mark.asyncio
    async def test_entity_not_in_matter_returns_not_found(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
    ) -> None:
        """Should return EntityNotFoundError when entity not in requested matter.

        This test verifies that a user cannot query statements for an entity
        that exists in a different matter.

        Attack scenario:
        1. User A has access to matter-A containing entity-X
        2. User B has access to matter-B (no entity-X)
        3. User B tries to query statements for entity-X via matter-B
        4. API should return NOT_FOUND (not statements from matter-A)
        """
        # Entity doesn't exist in the requested matter
        # (even if it exists in another matter, MIG validates matter_id)
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        with pytest.raises(EntityNotFoundError) as exc_info:
            await service.get_entity_statements(
                entity_id="entity-from-other-matter",
                matter_id="user-matter-without-entity",
            )

        assert exc_info.value.code == "ENTITY_NOT_FOUND"
        # Verify MIG was called with the user's matter_id
        mock_mig_service.get_entity.assert_called_once_with(
            "entity-from-other-matter",
            "user-matter-without-entity",
        )

    @pytest.mark.asyncio
    async def test_mig_validates_matter_before_query(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Should validate entity-matter relationship BEFORE running chunk query.

        The service must validate via MIG before running any database queries.
        This prevents information leakage even if the chunk query would
        technically be filtered by matter_id.
        """
        # Entity not found - validation should fail
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        with pytest.raises(EntityNotFoundError):
            await service.get_entity_statements(
                entity_id="any-entity",
                matter_id="any-matter",
            )

        # Engine should NEVER be called if validation fails
        mock_engine.get_statements_for_entity.assert_not_called()
        mock_engine.get_statements_for_canonical_entity.assert_not_called()
        mock_engine.count_statements_for_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_validates_matter_before_query(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Should validate entity-matter relationship for count queries too."""
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        with pytest.raises(EntityNotFoundError):
            await service.get_entity_statement_count(
                entity_id="any-entity",
                matter_id="any-matter",
            )

        # Engine count should not be called
        mock_engine.count_statements_for_entity.assert_not_called()


class TestContradictionCrossEntityIsolation:
    """Tests that alias resolution respects matter boundaries."""

    @pytest.fixture
    def mock_mig_service(self) -> MagicMock:
        """Create mock MIG service."""
        return MagicMock()

    @pytest.fixture
    def mock_engine(self) -> MagicMock:
        """Create mock engine."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_mig_service: MagicMock, mock_engine: MagicMock) -> StatementQueryService:
        """Create service instance with mocked dependencies."""
        svc = StatementQueryService()
        svc._mig_service = mock_mig_service
        svc._engine = mock_engine
        return svc

    @pytest.mark.asyncio
    async def test_alias_resolution_respects_matter_boundary(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Should only include aliases from the same matter.

        Even if Entity A in Matter-1 has the same canonical_name as
        Entity B in Matter-2, they should NOT be treated as aliases
        when querying within a single matter.
        """
        mock_entity = MagicMock()
        mock_entity.id = "entity-123"

        # Entity exists in matter
        mock_mig_service.get_entity = AsyncMock(return_value=mock_entity)

        # Mock engine to track what entity IDs are queried
        mock_engine.count_statements_for_entity = AsyncMock(return_value=0)
        mock_engine.get_statements_for_canonical_entity = AsyncMock(
            return_value=EntityStatements(
                entity_id="entity-123",
                entity_name="Test",
                total_statements=0,
                documents=[],
                aliases_included=[],
            )
        )

        await service.get_entity_statements(
            entity_id="entity-123",
            matter_id="matter-A",
            include_aliases=True,
        )

        # Verify MIG validates the matter_id
        mock_mig_service.get_entity.assert_called_with("entity-123", "matter-A")

        # Engine should receive the correct matter_id
        call_kwargs = mock_engine.get_statements_for_canonical_entity.call_args.kwargs
        assert call_kwargs["matter_id"] == "matter-A"
