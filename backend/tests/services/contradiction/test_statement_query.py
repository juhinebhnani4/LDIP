"""Tests for Statement Query Service.

Story 5-1: Service layer tests for entity statement querying.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.contradiction import EntityStatements
from app.services.contradiction.statement_query import (
    EntityNotFoundError,
    StatementQueryService,
    get_statement_query_service,
)


class TestStatementQueryService:
    """Tests for StatementQueryService."""

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
    async def test_get_entity_statements_entity_not_found(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
    ) -> None:
        """Should raise EntityNotFoundError when entity doesn't exist."""
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        with pytest.raises(EntityNotFoundError) as exc_info:
            await service.get_entity_statements(
                entity_id="nonexistent-entity",
                matter_id="matter-123",
            )

        assert exc_info.value.entity_id == "nonexistent-entity"
        assert exc_info.value.matter_id == "matter-123"
        assert exc_info.value.code == "ENTITY_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_entity_statements_validates_matter(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
    ) -> None:
        """Should validate entity belongs to matter (Layer 4 isolation)."""
        # Entity exists but in different matter - returns None
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        with pytest.raises(EntityNotFoundError):
            await service.get_entity_statements(
                entity_id="entity-123",
                matter_id="wrong-matter",
            )

        # Verify get_entity was called with both IDs
        mock_mig_service.get_entity.assert_called_once_with("entity-123", "wrong-matter")

    @pytest.mark.asyncio
    async def test_get_entity_statements_success(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Should return EntityStatementsResponse on success."""
        # Mock entity
        mock_entity = MagicMock()
        mock_entity.id = "entity-123"
        mock_entity.canonical_name = "Test Entity"

        # Mock engine response
        mock_statements = EntityStatements(
            entity_id="entity-123",
            entity_name="Test Entity",
            total_statements=5,
            documents=[],
            aliases_included=["Alias 1"],
        )

        mock_mig_service.get_entity = AsyncMock(return_value=mock_entity)
        mock_engine.count_statements_for_entity = AsyncMock(return_value=5)
        mock_engine.get_statements_for_canonical_entity = AsyncMock(
            return_value=mock_statements
        )

        result = await service.get_entity_statements(
            entity_id="entity-123",
            matter_id="matter-456",
            include_aliases=True,
        )

        assert result.data.entity_id == "entity-123"
        assert result.data.total_statements == 5
        assert result.meta.total == 5

    @pytest.mark.asyncio
    async def test_get_entity_statements_without_aliases(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Should call get_statements_for_entity when include_aliases=False."""
        mock_entity = MagicMock()
        mock_statements = EntityStatements(
            entity_id="entity-123",
            entity_name="Test",
            total_statements=0,
            documents=[],
            aliases_included=[],
        )

        mock_mig_service.get_entity = AsyncMock(return_value=mock_entity)
        mock_engine.count_statements_for_entity = AsyncMock(return_value=0)
        mock_engine.get_statements_for_entity = AsyncMock(
            return_value=mock_statements
        )

        await service.get_entity_statements(
            entity_id="entity-123",
            matter_id="matter-456",
            include_aliases=False,
        )

        # Verify it called get_statements_for_entity (not canonical)
        mock_engine.get_statements_for_entity.assert_called_once()
        mock_engine.get_statements_for_canonical_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_entity_statements_pagination(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Should return correct pagination metadata."""
        mock_entity = MagicMock()
        mock_statements = EntityStatements(
            entity_id="entity-123",
            entity_name="Test",
            total_statements=0,
            documents=[],
            aliases_included=[],
        )

        mock_mig_service.get_entity = AsyncMock(return_value=mock_entity)
        mock_engine.count_statements_for_entity = AsyncMock(return_value=120)
        mock_engine.get_statements_for_canonical_entity = AsyncMock(
            return_value=mock_statements
        )

        result = await service.get_entity_statements(
            entity_id="entity-123",
            matter_id="matter-456",
            page=2,
            per_page=50,
        )

        assert result.meta.total == 120
        assert result.meta.page == 2
        assert result.meta.per_page == 50
        assert result.meta.total_pages == 3  # ceil(120/50)

    @pytest.mark.asyncio
    async def test_get_entity_statement_count(
        self,
        service: StatementQueryService,
        mock_mig_service: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Should return statement count for entity."""
        mock_entity = MagicMock()

        mock_mig_service.get_entity = AsyncMock(return_value=mock_entity)
        mock_engine.count_statements_for_entity = AsyncMock(return_value=42)

        count = await service.get_entity_statement_count(
            entity_id="entity-123",
            matter_id="matter-456",
        )

        assert count == 42


class TestStatementQueryServiceFactory:
    """Tests for service factory function."""

    def test_singleton_factory(self) -> None:
        """Should return singleton instance."""
        get_statement_query_service.cache_clear()

        service1 = get_statement_query_service()
        service2 = get_statement_query_service()

        assert service1 is service2

        get_statement_query_service.cache_clear()
