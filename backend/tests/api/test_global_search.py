"""Unit tests for global search API routes.

Story 14.11: Global Search RAG Wiring

Tests:
- Authentication requirement
- Search returns only accessible matters
- Returns both matter and document results
- Respects limit parameter
- Query validation
- Error handling
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import app
from app.models.global_search import (
    GlobalSearchMeta,
    GlobalSearchResponse,
    GlobalSearchResultItem,
)
from app.services.global_search_service import (
    GlobalSearchService,
    GlobalSearchServiceError,
    get_global_search_service,
)

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
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def create_mock_search_result(
    result_type: str = "document",
    matter_id: str | None = None,
) -> GlobalSearchResultItem:
    """Create a mock global search result item."""
    matter_id = matter_id or str(uuid4())
    return GlobalSearchResultItem(
        id=str(uuid4()),
        type=result_type,
        title="Test Result" if result_type == "matter" else "Document (Page 5)",
        matter_id=matter_id,
        matter_title="Test Matter Title",
        matched_content="Test matched content for search result...",
    )


class TestGlobalSearchEndpoint:
    """Tests for GET /api/search endpoint."""

    @pytest.mark.anyio
    async def test_requires_authentication(self) -> None:
        """Should reject unauthenticated requests with 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/search?q=test")

        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_returns_results_for_authenticated_user(self) -> None:
        """Should return search results for authenticated user."""
        user_id = "test-user-id"
        matter_id = str(uuid4())

        # Mock search service
        mock_service = MagicMock(spec=GlobalSearchService)
        mock_response = GlobalSearchResponse(
            data=[
                create_mock_search_result("matter", matter_id),
                create_mock_search_result("document", matter_id),
            ],
            meta=GlobalSearchMeta(query="contract", total=2),
        )
        mock_service.search_across_matters = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token(user_id=user_id)
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=contract",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "meta" in data
            assert len(data["data"]) == 2
            assert data["meta"]["query"] == "contract"
            assert data["meta"]["total"] == 2

            # Verify service was called with correct parameters
            mock_service.search_across_matters.assert_called_once_with(
                user_id=user_id,
                query="contract",
                limit=20,  # default
            )
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_respects_limit_parameter(self) -> None:
        """Should pass limit parameter to service."""
        user_id = "test-user-id"

        mock_service = MagicMock(spec=GlobalSearchService)
        mock_response = GlobalSearchResponse(
            data=[create_mock_search_result("matter")],
            meta=GlobalSearchMeta(query="test", total=1),
        )
        mock_service.search_across_matters = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token(user_id=user_id)
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=test&limit=10",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200

            # Verify limit was passed
            mock_service.search_across_matters.assert_called_once_with(
                user_id=user_id,
                query="test",
                limit=10,
            )
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_validates_query_min_length(self) -> None:
        """Should reject queries shorter than 2 characters."""
        app.dependency_overrides[get_settings] = get_test_settings

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=a",  # Only 1 character
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 422  # Validation error
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_validates_limit_max(self) -> None:
        """Should reject limit greater than 50."""
        app.dependency_overrides[get_settings] = get_test_settings

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=test&limit=100",  # Exceeds max of 50
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_validates_limit_min(self) -> None:
        """Should reject limit less than 1."""
        app.dependency_overrides[get_settings] = get_test_settings

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=test&limit=0",  # Below min of 1
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


class TestGlobalSearchResultsFormat:
    """Tests for global search response format."""

    @pytest.mark.anyio
    async def test_returns_matter_results(self) -> None:
        """Should include matter results with correct format."""
        matter_id = str(uuid4())

        mock_service = MagicMock(spec=GlobalSearchService)
        mock_response = GlobalSearchResponse(
            data=[
                GlobalSearchResultItem(
                    id=matter_id,
                    type="matter",
                    title="Smith vs. Jones",
                    matter_id=matter_id,
                    matter_title="Smith vs. Jones",
                    matched_content="Contract dispute...",
                ),
            ],
            meta=GlobalSearchMeta(query="smith", total=1),
        )
        mock_service.search_across_matters = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=smith",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            result = data["data"][0]

            # Check camelCase aliases
            assert result["type"] == "matter"
            assert result["title"] == "Smith vs. Jones"
            assert result["matterId"] == matter_id
            assert result["matterTitle"] == "Smith vs. Jones"
            assert result["matchedContent"] == "Contract dispute..."
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_document_results(self) -> None:
        """Should include document results with correct format."""
        matter_id = str(uuid4())
        doc_id = str(uuid4())

        mock_service = MagicMock(spec=GlobalSearchService)
        mock_response = GlobalSearchResponse(
            data=[
                GlobalSearchResultItem(
                    id=doc_id,
                    type="document",
                    title="Document (Page 5)",
                    matter_id=matter_id,
                    matter_title="Smith vs. Jones",
                    matched_content="...terms of agreement...",
                ),
            ],
            meta=GlobalSearchMeta(query="agreement", total=1),
        )
        mock_service.search_across_matters = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=agreement",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            result = data["data"][0]

            assert result["type"] == "document"
            assert result["id"] == doc_id
            assert result["matterId"] == matter_id
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_empty_results_for_no_matches(self) -> None:
        """Should return empty array when no results found."""
        mock_service = MagicMock(spec=GlobalSearchService)
        mock_response = GlobalSearchResponse(
            data=[],
            meta=GlobalSearchMeta(query="xyz123", total=0),
        )
        mock_service.search_across_matters = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=xyz123",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["data"] == []
            assert data["meta"]["total"] == 0
        finally:
            app.dependency_overrides.clear()


class TestGlobalSearchErrorHandling:
    """Tests for global search error handling."""

    @pytest.mark.anyio
    async def test_returns_503_on_database_error(self) -> None:
        """Should return 503 when database is not configured."""
        mock_service = MagicMock(spec=GlobalSearchService)
        mock_service.search_across_matters = AsyncMock(
            side_effect=GlobalSearchServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=test",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["error"]["code"] == "DATABASE_NOT_CONFIGURED"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_500_on_unexpected_error(self) -> None:
        """Should return 500 on unexpected errors."""
        mock_service = MagicMock(spec=GlobalSearchService)
        mock_service.search_across_matters = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=test",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 500
            data = response.json()
            assert data["detail"]["error"]["code"] == "SEARCH_FAILED"
        finally:
            app.dependency_overrides.clear()


class TestGlobalSearchMatterIsolation:
    """Tests for matter access control in global search.

    These tests verify that:
    1. User ID is extracted from auth token (not request)
    2. Service receives correct user_id for access filtering
    """

    @pytest.mark.anyio
    async def test_passes_user_id_from_token_to_service(self) -> None:
        """Should pass authenticated user ID to search service."""
        expected_user_id = "specific-user-uuid-1234"

        mock_service = MagicMock(spec=GlobalSearchService)
        mock_response = GlobalSearchResponse(
            data=[],
            meta=GlobalSearchMeta(query="test", total=0),
        )
        mock_service.search_across_matters = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            token = create_test_token(user_id=expected_user_id)
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/search?q=test",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200

            # Verify service was called with correct user_id
            call_kwargs = mock_service.search_across_matters.call_args[1]
            assert call_kwargs["user_id"] == expected_user_id
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_different_users_get_different_results(self) -> None:
        """Should call service with different user IDs for different tokens.

        This test verifies that the endpoint correctly extracts user_id
        from the JWT token, not from request parameters.
        """
        user1_id = "user-1-uuid"
        user2_id = "user-2-uuid"

        mock_service = MagicMock(spec=GlobalSearchService)
        mock_response = GlobalSearchResponse(
            data=[],
            meta=GlobalSearchMeta(query="test", total=0),
        )
        mock_service.search_across_matters = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_global_search_service] = lambda: mock_service

        try:
            # First request as user1
            token1 = create_test_token(user_id=user1_id)
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                await client.get(
                    "/api/search?q=test",
                    headers={"Authorization": f"Bearer {token1}"},
                )

            # Second request as user2
            token2 = create_test_token(user_id=user2_id)
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                await client.get(
                    "/api/search?q=test",
                    headers={"Authorization": f"Bearer {token2}"},
                )

            # Verify both calls with different user_ids
            calls = mock_service.search_across_matters.call_args_list
            assert len(calls) == 2
            assert calls[0][1]["user_id"] == user1_id
            assert calls[1][1]["user_id"] == user2_id
        finally:
            app.dependency_overrides.clear()
