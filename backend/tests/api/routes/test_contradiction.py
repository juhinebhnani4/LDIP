"""Tests for Contradiction API routes.

Story 5-1: API endpoint tests for entity statement querying.

Uses FastAPI dependency_overrides for proper test isolation.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.contradiction import (
    DocumentStatements,
    EntityStatements,
    EntityStatementsResponse,
    PaginationMeta,
    Statement,
    StatementValue,
    StatementValueType,
)
from app.models.matter import MatterRole
from app.services.contradiction.statement_query import EntityNotFoundError


# Test JWT secret
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


def get_test_settings() -> Settings:
    """Create test settings with JWT secret configured."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_anon_key = "test-anon-key"
    settings.is_configured = True
    settings.debug = True
    return settings


def create_test_token(
    user_id: str = "test-user-id",
    email: str = "test@example.com",
) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def sync_client() -> TestClient:
    """Create synchronous test client for auth tests."""
    return TestClient(app)


class TestGetEntityStatementsAuth:
    """Tests for authentication requirements."""

    def test_get_entity_statements_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.get(
            "/api/matters/matter-123/contradictions/entities/entity-123/statements"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetEntityStatements:
    """Tests for GET /api/matters/{matter_id}/contradictions/entities/{entity_id}/statements."""

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

    @pytest.mark.anyio
    async def test_get_entity_statements_success(
        self,
        mock_service_response: EntityStatementsResponse,
    ) -> None:
        """Should return 200 with entity statements on success."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service

        # Mock matter service for auth
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        # Mock statement query service
        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=mock_service_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        assert data["data"]["entityId"] == "entity-123"
        assert data["data"]["entityName"] == "Nirav Jobalia"
        assert data["data"]["totalStatements"] == 2
        assert len(data["data"]["documents"]) == 1

    @pytest.mark.anyio
    async def test_get_entity_statements_not_found(self) -> None:
        """Should return 404 when entity not found."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(side_effect=EntityNotFoundError(
            "entity-123", "matter-123"
        ))

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.anyio
    async def test_get_entity_statements_with_query_params(
        self,
        mock_service_response: EntityStatementsResponse,
    ) -> None:
        """Should pass query parameters to service."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=mock_service_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                params={
                    "includeAliases": "false",
                    "page": 2,
                    "perPage": 25,
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        # Verify service was called with correct params
        call_args = mock_stmt_service.get_entity_statements.call_args
        assert call_args.kwargs["include_aliases"] is False
        assert call_args.kwargs["page"] == 2
        assert call_args.kwargs["per_page"] == 25

    @pytest.mark.anyio
    async def test_get_entity_statements_empty_result(self) -> None:
        """Should return 200 with empty statements (AC #4)."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service

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

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=empty_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        # Should return 200, not 404 (AC #4)
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["totalStatements"] == 0
        assert len(data["data"]["documents"]) == 0


class TestGetEntityStatementsValueExtraction:
    """Tests for value extraction in API responses (AC #3)."""

    @pytest.mark.anyio
    async def test_response_includes_extracted_dates(self) -> None:
        """Should include extracted dates in statements."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service

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

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=response_with_dates)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        statement = data["data"]["documents"][0]["statements"][0]
        assert len(statement["dates"]) == 1
        assert statement["dates"][0]["type"] == "DATE"
        assert statement["dates"][0]["normalized"] == "2024-01-15"

    @pytest.mark.anyio
    async def test_response_includes_extracted_amounts(self) -> None:
        """Should include extracted amounts in statements."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service

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

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=response_with_amounts)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        statement = data["data"]["documents"][0]["statements"][0]
        assert len(statement["amounts"]) == 1
        assert statement["amounts"][0]["type"] == "AMOUNT"
        assert statement["amounts"][0]["normalized"] == "500000"


class TestGetEntityStatementsAliasResolution:
    """Tests for alias resolution in API responses (AC #2)."""

    @pytest.mark.anyio
    async def test_response_includes_aliases_searched(self) -> None:
        """Should include aliasesIncluded in response."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service

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

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=response_with_aliases)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                params={"includeAliases": "true"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        assert "N.D. Jobalia" in data["data"]["aliasesIncluded"]
        assert "Nirav D. Jobalia" in data["data"]["aliasesIncluded"]
