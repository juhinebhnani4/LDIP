"""Tests for Contradiction API routes.

Story 5-1: API endpoint tests for entity statement querying.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.contradiction import (
    DocumentStatements,
    EntityStatements,
    EntityStatementsResponse,
    PaginationMeta,
    Statement,
    StatementValue,
    StatementValueType,
)
from app.services.contradiction.statement_query import EntityNotFoundError


class TestGetEntityStatements:
    """Tests for GET /api/matters/{matter_id}/contradictions/entities/{entity_id}/statements."""

    @pytest.fixture
    def mock_membership(self) -> MagicMock:
        """Create mock membership dependency."""
        membership = MagicMock()
        membership.user_id = "test-user-id"
        membership.matter_id = "test-matter-id"
        membership.role = "editor"
        return membership

    @pytest.fixture
    def mock_service_response(self) -> EntityStatementsResponse:
        """Create mock service response."""
        return EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Nirav Jobalia",
                total_statements=2,
                documents=[
                    DocumentStatements(
                        document_id="doc-1",
                        document_name="Contract.pdf",
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id="chunk-1",
                                document_id="doc-1",
                                content="On 15/01/2024, payment of Rs. 5,00,000 was made.",
                                dates=[
                                    StatementValue(
                                        type=StatementValueType.DATE,
                                        raw_text="15/01/2024",
                                        normalized="2024-01-15",
                                        confidence=0.9,
                                    )
                                ],
                                amounts=[
                                    StatementValue(
                                        type=StatementValueType.AMOUNT,
                                        raw_text="Rs. 5,00,000",
                                        normalized="500000",
                                        confidence=0.9,
                                    )
                                ],
                                page_number=1,
                                confidence=1.0,
                            )
                        ],
                        statement_count=1,
                    )
                ],
                aliases_included=["N.D. Jobalia"],
            ),
            meta=PaginationMeta(
                total=2,
                page=1,
                per_page=50,
                total_pages=1,
            ),
        )

    @pytest.mark.asyncio
    async def test_get_entity_statements_success(
        self,
        client: AsyncClient,
        mock_membership: MagicMock,
        mock_service_response: EntityStatementsResponse,
    ) -> None:
        """Should return 200 with entity statements on success."""
        with (
            patch("app.api.routes.contradiction.require_matter_role") as mock_role,
            patch("app.api.routes.contradiction.get_statement_query_service") as mock_get_service,
        ):
            # Mock authentication
            mock_role.return_value = lambda: mock_membership

            # Mock service
            mock_service = MagicMock()
            mock_service.get_entity_statements = AsyncMock(
                return_value=mock_service_response
            )
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200

            data = response.json()
            assert data["data"]["entityId"] == "entity-123"
            assert data["data"]["entityName"] == "Nirav Jobalia"
            assert data["data"]["totalStatements"] == 2
            assert len(data["data"]["documents"]) == 1

    @pytest.mark.asyncio
    async def test_get_entity_statements_not_found(
        self,
        client: AsyncClient,
        mock_membership: MagicMock,
    ) -> None:
        """Should return 404 when entity not found."""
        with (
            patch("app.api.routes.contradiction.require_matter_role") as mock_role,
            patch("app.api.routes.contradiction.get_statement_query_service") as mock_get_service,
        ):
            mock_role.return_value = lambda: mock_membership

            mock_service = MagicMock()
            mock_service.get_entity_statements = AsyncMock(
                side_effect=EntityNotFoundError("entity-123", "matter-123")
            )
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["error"]["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_entity_statements_with_query_params(
        self,
        client: AsyncClient,
        mock_membership: MagicMock,
        mock_service_response: EntityStatementsResponse,
    ) -> None:
        """Should pass query parameters to service."""
        with (
            patch("app.api.routes.contradiction.require_matter_role") as mock_role,
            patch("app.api.routes.contradiction.get_statement_query_service") as mock_get_service,
        ):
            mock_role.return_value = lambda: mock_membership

            mock_service = MagicMock()
            mock_service.get_entity_statements = AsyncMock(
                return_value=mock_service_response
            )
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                params={
                    "includeAliases": "false",
                    "page": 2,
                    "perPage": 25,
                },
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200

            # Verify service was called with correct params
            call_args = mock_service.get_entity_statements.call_args
            assert call_args.kwargs["include_aliases"] is False
            assert call_args.kwargs["page"] == 2
            assert call_args.kwargs["per_page"] == 25

    @pytest.mark.asyncio
    async def test_get_entity_statements_empty_result(
        self,
        client: AsyncClient,
        mock_membership: MagicMock,
    ) -> None:
        """Should return 200 with empty statements (AC #4)."""
        empty_response = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test Entity",
                total_statements=0,
                documents=[],
                aliases_included=[],
            ),
            meta=PaginationMeta(
                total=0,
                page=1,
                per_page=50,
                total_pages=0,
            ),
        )

        with (
            patch("app.api.routes.contradiction.require_matter_role") as mock_role,
            patch("app.api.routes.contradiction.get_statement_query_service") as mock_get_service,
        ):
            mock_role.return_value = lambda: mock_membership

            mock_service = MagicMock()
            mock_service.get_entity_statements = AsyncMock(return_value=empty_response)
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": "Bearer test-token"},
            )

            # Should return 200, not 404 (AC #4)
            assert response.status_code == 200

            data = response.json()
            assert data["data"]["totalStatements"] == 0
            assert len(data["data"]["documents"]) == 0


class TestGetEntityStatementsValueExtraction:
    """Tests for value extraction in API responses (AC #3)."""

    @pytest.fixture
    def mock_membership(self) -> MagicMock:
        """Create mock membership dependency."""
        membership = MagicMock()
        membership.user_id = "test-user-id"
        return membership

    @pytest.mark.asyncio
    async def test_response_includes_extracted_dates(
        self,
        client: AsyncClient,
        mock_membership: MagicMock,
    ) -> None:
        """Should include extracted dates in statements."""
        response_with_dates = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test",
                total_statements=1,
                documents=[
                    DocumentStatements(
                        document_id="doc-1",
                        document_name=None,
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id="chunk-1",
                                document_id="doc-1",
                                content="On 15/01/2024.",
                                dates=[
                                    StatementValue(
                                        type=StatementValueType.DATE,
                                        raw_text="15/01/2024",
                                        normalized="2024-01-15",
                                        confidence=0.9,
                                    )
                                ],
                                amounts=[],
                                page_number=1,
                                confidence=1.0,
                            )
                        ],
                        statement_count=1,
                    )
                ],
                aliases_included=[],
            ),
            meta=PaginationMeta(total=1, page=1, per_page=50, total_pages=1),
        )

        with (
            patch("app.api.routes.contradiction.require_matter_role") as mock_role,
            patch("app.api.routes.contradiction.get_statement_query_service") as mock_get_service,
        ):
            mock_role.return_value = lambda: mock_membership

            mock_service = MagicMock()
            mock_service.get_entity_statements = AsyncMock(
                return_value=response_with_dates
            )
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200

            data = response.json()
            statement = data["data"]["documents"][0]["statements"][0]
            assert len(statement["dates"]) == 1
            assert statement["dates"][0]["type"] == "DATE"
            assert statement["dates"][0]["normalized"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_response_includes_extracted_amounts(
        self,
        client: AsyncClient,
        mock_membership: MagicMock,
    ) -> None:
        """Should include extracted amounts in statements."""
        response_with_amounts = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test",
                total_statements=1,
                documents=[
                    DocumentStatements(
                        document_id="doc-1",
                        document_name=None,
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id="chunk-1",
                                document_id="doc-1",
                                content="Payment of 5 lakhs.",
                                dates=[],
                                amounts=[
                                    StatementValue(
                                        type=StatementValueType.AMOUNT,
                                        raw_text="5 lakhs",
                                        normalized="500000",
                                        confidence=0.9,
                                    )
                                ],
                                page_number=1,
                                confidence=1.0,
                            )
                        ],
                        statement_count=1,
                    )
                ],
                aliases_included=[],
            ),
            meta=PaginationMeta(total=1, page=1, per_page=50, total_pages=1),
        )

        with (
            patch("app.api.routes.contradiction.require_matter_role") as mock_role,
            patch("app.api.routes.contradiction.get_statement_query_service") as mock_get_service,
        ):
            mock_role.return_value = lambda: mock_membership

            mock_service = MagicMock()
            mock_service.get_entity_statements = AsyncMock(
                return_value=response_with_amounts
            )
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200

            data = response.json()
            statement = data["data"]["documents"][0]["statements"][0]
            assert len(statement["amounts"]) == 1
            assert statement["amounts"][0]["type"] == "AMOUNT"
            assert statement["amounts"][0]["normalized"] == "500000"


class TestGetEntityStatementsAliasResolution:
    """Tests for alias resolution in API responses (AC #2)."""

    @pytest.fixture
    def mock_membership(self) -> MagicMock:
        """Create mock membership dependency."""
        membership = MagicMock()
        membership.user_id = "test-user-id"
        return membership

    @pytest.mark.asyncio
    async def test_response_includes_aliases_searched(
        self,
        client: AsyncClient,
        mock_membership: MagicMock,
    ) -> None:
        """Should include aliasesIncluded in response."""
        response_with_aliases = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Nirav Jobalia",
                total_statements=3,
                documents=[],
                aliases_included=["N.D. Jobalia", "Nirav D. Jobalia"],
            ),
            meta=PaginationMeta(total=3, page=1, per_page=50, total_pages=1),
        )

        with (
            patch("app.api.routes.contradiction.require_matter_role") as mock_role,
            patch("app.api.routes.contradiction.get_statement_query_service") as mock_get_service,
        ):
            mock_role.return_value = lambda: mock_membership

            mock_service = MagicMock()
            mock_service.get_entity_statements = AsyncMock(
                return_value=response_with_aliases
            )
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                params={"includeAliases": "true"},
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200

            data = response.json()
            assert "N.D. Jobalia" in data["data"]["aliasesIncluded"]
            assert "Nirav D. Jobalia" in data["data"]["aliasesIncluded"]
