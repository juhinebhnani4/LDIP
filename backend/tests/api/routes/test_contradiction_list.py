"""Tests for Contradiction List API routes.

Story 14.2: Contradictions List API Endpoint

Test Categories:
- Authentication requirements
- Endpoint existence and routing
- Filtering support
- Pagination
- Sorting
- Response format validation
- Error handling
- Empty results
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
    ContradictionType,
    PaginationMeta,
    SeverityLevel,
)
from app.models.contradiction_list import (
    ContradictionEvidenceLink,
    ContradictionItem,
    ContradictionsListResponse,
    EntityContradictions,
    StatementInfo,
)
from app.models.matter import MatterRole


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


@pytest.fixture
def mock_service_response() -> ContradictionsListResponse:
    """Create mock service response with sample contradictions."""
    return ContradictionsListResponse(
        data=[
            EntityContradictions(
                entity_id="entity-123",
                entity_name="Nirav Jobalia",
                contradictions=[
                    ContradictionItem(
                        id="contradiction-1",
                        contradiction_type=ContradictionType.AMOUNT_MISMATCH,
                        severity=SeverityLevel.HIGH,
                        entity_id="entity-123",
                        entity_name="Nirav Jobalia",
                        statement_a=StatementInfo(
                            document_id="doc-1",
                            document_name="Contract.pdf",
                            page=5,
                            excerpt="The loan amount was Rs. 5 lakhs.",
                            date=None,
                        ),
                        statement_b=StatementInfo(
                            document_id="doc-2",
                            document_name="Agreement.pdf",
                            page=12,
                            excerpt="The loan amount was Rs. 8 lakhs.",
                            date=None,
                        ),
                        explanation="Statement A claims loan was Rs. 5 lakhs. Statement B claims Rs. 8 lakhs. These amounts conflict.",
                        evidence_links=[
                            ContradictionEvidenceLink(
                                statement_id="chunk-1",
                                document_id="doc-1",
                                document_name="Contract.pdf",
                                page=5,
                                bbox_ids=[],
                            ),
                            ContradictionEvidenceLink(
                                statement_id="chunk-2",
                                document_id="doc-2",
                                document_name="Agreement.pdf",
                                page=12,
                                bbox_ids=[],
                            ),
                        ],
                        confidence=0.95,
                        created_at="2026-01-15T10:00:00Z",
                    ),
                ],
                count=1,
            ),
            EntityContradictions(
                entity_id="entity-456",
                entity_name="John Smith",
                contradictions=[
                    ContradictionItem(
                        id="contradiction-2",
                        contradiction_type=ContradictionType.DATE_MISMATCH,
                        severity=SeverityLevel.MEDIUM,
                        entity_id="entity-456",
                        entity_name="John Smith",
                        statement_a=StatementInfo(
                            document_id="doc-1",
                            document_name="Contract.pdf",
                            page=3,
                            excerpt="The contract was signed on 15/01/2024.",
                            date="2024-01-15",
                        ),
                        statement_b=StatementInfo(
                            document_id="doc-3",
                            document_name="Affidavit.pdf",
                            page=1,
                            excerpt="The contract was signed on 15/06/2024.",
                            date="2024-06-15",
                        ),
                        explanation="Different signing dates reported.",
                        evidence_links=[],
                        confidence=0.88,
                        created_at="2026-01-15T09:00:00Z",
                    ),
                ],
                count=1,
            ),
        ],
        meta=PaginationMeta(
            total=2,
            page=1,
            per_page=20,
            total_pages=1,
        ),
    )


@pytest.fixture
def mock_empty_response() -> ContradictionsListResponse:
    """Create mock empty response."""
    return ContradictionsListResponse(
        data=[],
        meta=PaginationMeta(
            total=0,
            page=1,
            per_page=20,
            total_pages=0,
        ),
    )


# =============================================================================
# Authentication Tests (AC #1)
# =============================================================================


class TestContradictionListAuth:
    """Tests for authentication requirements."""

    def test_get_contradictions_requires_auth(self, sync_client: TestClient) -> None:
        """Should return 401 without authentication."""
        response = sync_client.get("/api/matters/matter-123/contradictions")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_contradictions_invalid_token(self, sync_client: TestClient) -> None:
        """Should return 401 with invalid token."""
        response = sync_client.get(
            "/api/matters/matter-123/contradictions",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Success Tests (AC #1, #2)
# =============================================================================


class TestGetAllContradictions:
    """Tests for GET /api/matters/{matter_id}/contradictions."""

    @pytest.mark.anyio
    async def test_returns_contradictions_grouped_by_entity(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should return 200 with entity-grouped contradictions."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) == 2

        # Verify first entity group
        first_entity = data["data"][0]
        assert first_entity["entityId"] == "entity-123"
        assert first_entity["entityName"] == "Nirav Jobalia"
        assert first_entity["count"] == 1

        # Verify contradiction structure
        contradiction = first_entity["contradictions"][0]
        assert contradiction["contradictionType"] == "amount_mismatch"
        assert contradiction["severity"] == "high"
        assert "statementA" in contradiction
        assert "statementB" in contradiction
        assert "explanation" in contradiction
        assert "evidenceLinks" in contradiction

    @pytest.mark.anyio
    async def test_response_includes_pagination_meta(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should include pagination metadata in response."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        meta = data["meta"]
        assert meta["total"] == 2
        assert meta["page"] == 1
        assert meta["perPage"] == 20
        assert meta["totalPages"] == 1


# =============================================================================
# Filter Tests (AC #3)
# =============================================================================


class TestContradictionFiltering:
    """Tests for filtering support."""

    @pytest.mark.anyio
    async def test_filter_by_severity(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should pass severity filter to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                params={"severity": "high"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        # Verify service was called with severity filter
        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["severity"] == "high"

    @pytest.mark.anyio
    async def test_filter_by_contradiction_type(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should pass contradictionType filter to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                params={"contradictionType": "date_mismatch"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["contradiction_type"] == "date_mismatch"

    @pytest.mark.anyio
    async def test_filter_by_entity_id(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should pass entityId filter to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                params={"entityId": "entity-123"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["entity_id"] == "entity-123"

    @pytest.mark.anyio
    async def test_filter_by_document_id(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should pass documentId filter to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                params={"documentId": "doc-1"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["document_id"] == "doc-1"


# =============================================================================
# Pagination Tests (AC #4)
# =============================================================================


class TestContradictionPagination:
    """Tests for pagination support."""

    @pytest.mark.anyio
    async def test_pagination_params_passed_to_service(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should pass page and perPage to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                params={"page": 2, "perPage": 10},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["page"] == 2
        assert call_args.kwargs["per_page"] == 10

    @pytest.mark.anyio
    async def test_default_pagination_values(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should use default page=1, perPage=20."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["page"] == 1
        assert call_args.kwargs["per_page"] == 20


# =============================================================================
# Sorting Tests (AC #6)
# =============================================================================


class TestContradictionSorting:
    """Tests for sorting support."""

    @pytest.mark.anyio
    async def test_sort_by_severity_desc(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should pass sortBy and sortOrder to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                params={"sortBy": "severity", "sortOrder": "desc"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["sort_by"] == "severity"
        assert call_args.kwargs["sort_order"] == "desc"

    @pytest.mark.anyio
    async def test_sort_by_created_at_asc(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Should support sorting by createdAt ascending."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                params={"sortBy": "createdAt", "sortOrder": "asc"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        call_args = mock_list_service.get_all_contradictions.call_args
        assert call_args.kwargs["sort_by"] == "createdAt"
        assert call_args.kwargs["sort_order"] == "asc"


# =============================================================================
# Empty Results Tests (AC #4.11)
# =============================================================================


class TestEmptyResults:
    """Tests for empty result handling."""

    @pytest.mark.anyio
    async def test_empty_contradictions_returns_200(
        self,
        mock_empty_response: ContradictionsListResponse,
    ) -> None:
        """Should return 200 with empty list, not 404."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_empty_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        # Should return 200 with empty data, not error
        assert response.status_code == 200

        data = response.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0
        assert data["meta"]["totalPages"] == 0


# =============================================================================
# Error Handling Tests (AC #1)
# =============================================================================


class TestContradictionListErrorHandling:
    """Tests for error handling."""

    @pytest.mark.anyio
    async def test_service_error_returns_500(self) -> None:
        """Service error should return 500."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings
        from app.services.contradiction_list_service import (
            ContradictionListServiceError,
        )

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        error = ContradictionListServiceError(
            "Query failed", code="QUERY_FAILED", status_code=500
        )
        mock_list_service.get_all_contradictions = AsyncMock(side_effect=error)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 500

        data = response.json()
        assert data["detail"]["error"]["code"] == "QUERY_FAILED"

    @pytest.mark.anyio
    async def test_unexpected_error_returns_500(self) -> None:
        """Unexpected error should return 500 with generic message."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 500

        data = response.json()
        assert data["detail"]["error"]["code"] == "INTERNAL_ERROR"


# =============================================================================
# Response Structure Tests (AC #2)
# =============================================================================


class TestContradictionResponseStructure:
    """Tests for response structure validation."""

    @pytest.mark.anyio
    async def test_statement_info_includes_all_fields(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Statement info should include document, page, excerpt, date."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        contradiction = data["data"][0]["contradictions"][0]

        # Check statement A
        stmt_a = contradiction["statementA"]
        assert "documentId" in stmt_a
        assert "documentName" in stmt_a
        assert "page" in stmt_a
        assert "excerpt" in stmt_a
        assert "date" in stmt_a

        # Check statement B
        stmt_b = contradiction["statementB"]
        assert "documentId" in stmt_b
        assert "documentName" in stmt_b

    @pytest.mark.anyio
    async def test_evidence_links_structure(
        self,
        mock_service_response: ContradictionsListResponse,
    ) -> None:
        """Evidence links should include document and bbox info."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_contradiction_list_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_list_service = MagicMock()
        mock_list_service.get_all_contradictions = AsyncMock(
            return_value=mock_service_response
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_contradiction_list_service] = (
            lambda: mock_list_service
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        contradiction = data["data"][0]["contradictions"][0]
        evidence_links = contradiction["evidenceLinks"]

        assert len(evidence_links) == 2

        link = evidence_links[0]
        assert "statementId" in link
        assert "documentId" in link
        assert "documentName" in link
        assert "page" in link
        assert "bboxIds" in link


# =============================================================================
# Model Serialization Tests
# =============================================================================


class TestContradictionModelSerialization:
    """Tests for model serialization."""

    def test_contradiction_item_serialization(self) -> None:
        """ContradictionItem should serialize with camelCase."""
        item = ContradictionItem(
            id="test-id",
            contradiction_type=ContradictionType.SEMANTIC_CONTRADICTION,
            severity=SeverityLevel.LOW,
            entity_id="entity-1",
            entity_name="Test Entity",
            statement_a=StatementInfo(
                document_id="doc-1",
                document_name="Doc.pdf",
                page=1,
                excerpt="Test",
                date=None,
            ),
            statement_b=StatementInfo(
                document_id="doc-2",
                document_name="Doc2.pdf",
                page=2,
                excerpt="Test2",
                date=None,
            ),
            explanation="Explanation",
            evidence_links=[],
            confidence=0.9,
            created_at="2026-01-15T10:00:00Z",
        )

        json_data = item.model_dump(by_alias=True)

        assert "contradictionType" in json_data
        assert "entityId" in json_data
        assert "entityName" in json_data
        assert "statementA" in json_data
        assert "statementB" in json_data
        assert "evidenceLinks" in json_data
        assert "createdAt" in json_data

    def test_entity_contradictions_serialization(self) -> None:
        """EntityContradictions should serialize with camelCase."""
        entity = EntityContradictions(
            entity_id="entity-1",
            entity_name="Test",
            contradictions=[],
            count=0,
        )

        json_data = entity.model_dump(by_alias=True)

        assert "entityId" in json_data
        assert "entityName" in json_data

    def test_pagination_meta_serialization(self) -> None:
        """PaginationMeta should serialize with camelCase."""
        meta = PaginationMeta(
            total=100,
            page=2,
            per_page=20,
            total_pages=5,
        )

        json_data = meta.model_dump(by_alias=True)

        assert "perPage" in json_data
        assert "totalPages" in json_data
