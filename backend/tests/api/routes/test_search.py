"""Unit tests for search API routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_matter_service
from app.core.config import Settings, get_settings
from app.main import app
from app.models.matter import MatterRole
from app.services.rag.hybrid_search import (
    HybridSearchResult,
    HybridSearchServiceError,
    SearchResult,
    SearchWeights,
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
    matter_id: str,
    bm25_rank: int | None = 1,
    semantic_rank: int | None = 2,
) -> SearchResult:
    """Create a mock search result for testing."""
    return SearchResult(
        id=str(uuid4()),
        matter_id=matter_id,
        document_id=str(uuid4()),
        content="Test legal content about contract termination.",
        page_number=5,
        chunk_type="child",
        token_count=150,
        bm25_rank=bm25_rank,
        semantic_rank=semantic_rank,
        rrf_score=0.032,
    )


def create_mock_matter_service(role: MatterRole | None = MatterRole.VIEWER) -> MagicMock:
    """Create a mock matter service for testing."""
    mock_service = MagicMock()
    mock_service.get_user_role.return_value = role
    return mock_service


class TestHybridSearchEndpoint:
    """Tests for POST /api/matters/{matter_id}/search endpoint."""

    @pytest.mark.anyio
    async def test_returns_hybrid_results_on_success(self) -> None:
        """Should return hybrid search results when authorized."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "test-user-id"

        # Mock search service
        mock_search_service = MagicMock()
        mock_result = HybridSearchResult(
            query="contract termination",
            matter_id=matter_id,
            results=[create_mock_search_result(matter_id)],
            total_candidates=10,
            weights=SearchWeights(bm25=1.0, semantic=1.0),
        )
        mock_search_service.search = AsyncMock(return_value=mock_result)

        # Set up dependency overrides for FastAPI deps
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            # Patch the search service factory (uses lru_cache, not FastAPI Depends)
            with patch(
                "app.api.routes.search.get_hybrid_search_service",
                return_value=mock_search_service,
            ):
                token = create_test_token(user_id=user_id)
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/search",
                        json={
                            "query": "contract termination",
                            "limit": 20,
                            "bm25_weight": 1.0,
                            "semantic_weight": 1.0,
                        },
                        headers={"Authorization": f"Bearer {token}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert "data" in data
                assert "meta" in data
                assert len(data["data"]) == 1
                assert data["meta"]["query"] == "contract termination"
                assert data["meta"]["matter_id"] == matter_id
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_validates_query_length(self) -> None:
        """Should reject empty queries."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={
                        "query": "",  # Empty query
                        "limit": 20,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 422  # Validation error
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_validates_limit_range(self) -> None:
        """Should reject limit outside valid range."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={
                        "query": "test query",
                        "limit": 200,  # Exceeds max of 100
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_validates_weight_range(self) -> None:
        """Should reject weights outside 0-2 range."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={
                        "query": "test query",
                        "bm25_weight": 3.0,  # Exceeds max of 2.0
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_requires_authentication(self) -> None:
        """Should reject unauthenticated requests."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/matters/{matter_id}/search",
                json={"query": "test"},
            )

        assert response.status_code == 401


class TestBM25SearchEndpoint:
    """Tests for POST /api/matters/{matter_id}/search/bm25 endpoint."""

    @pytest.mark.anyio
    async def test_returns_bm25_results_on_success(self) -> None:
        """Should return BM25-only search results when authorized."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        # Mock search service
        mock_search_service = MagicMock()
        mock_results = [create_mock_search_result(matter_id, bm25_rank=1, semantic_rank=None)]
        mock_search_service.bm25_search = AsyncMock(return_value=mock_results)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            with patch(
                "app.api.routes.search.get_hybrid_search_service",
                return_value=mock_search_service,
            ):
                token = create_test_token()
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/search/bm25",
                        json={
                            "query": "Section 138 NI Act",
                            "limit": 30,
                        },
                        headers={"Authorization": f"Bearer {token}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["meta"]["search_type"] == "bm25"
                assert len(data["data"]) == 1
        finally:
            app.dependency_overrides.clear()


class TestSemanticSearchEndpoint:
    """Tests for POST /api/matters/{matter_id}/search/semantic endpoint."""

    @pytest.mark.anyio
    async def test_returns_semantic_results_on_success(self) -> None:
        """Should return semantic-only search results when authorized."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        # Mock search service
        mock_search_service = MagicMock()
        mock_results = [create_mock_search_result(matter_id, bm25_rank=None, semantic_rank=1)]
        mock_search_service.semantic_search = AsyncMock(return_value=mock_results)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            with patch(
                "app.api.routes.search.get_hybrid_search_service",
                return_value=mock_search_service,
            ):
                token = create_test_token()
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/search/semantic",
                        json={
                            "query": "breach of contract remedies",
                            "limit": 30,
                        },
                        headers={"Authorization": f"Bearer {token}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["meta"]["search_type"] == "semantic"
                assert len(data["data"]) == 1
        finally:
            app.dependency_overrides.clear()


class TestSearchErrorHandling:
    """Tests for search endpoint error handling."""

    @pytest.mark.anyio
    async def test_returns_400_on_invalid_parameter(self) -> None:
        """Should return 400 on invalid parameter error."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        mock_search_service = MagicMock()
        mock_search_service.search = AsyncMock(
            side_effect=HybridSearchServiceError(
                message="Invalid matter_id",
                code="INVALID_PARAMETER",
            )
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            with patch(
                "app.api.routes.search.get_hybrid_search_service",
                return_value=mock_search_service,
            ):
                token = create_test_token()
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/search",
                        json={"query": "test"},
                        headers={"Authorization": f"Bearer {token}"},
                    )

                assert response.status_code == 400
                data = response.json()
                assert data["error"]["code"] == "INVALID_PARAMETER"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_503_on_database_not_configured(self) -> None:
        """Should return 503 when database is not configured."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        mock_search_service = MagicMock()
        mock_search_service.search = AsyncMock(
            side_effect=HybridSearchServiceError(
                message="Database not configured",
                code="DATABASE_NOT_CONFIGURED",
            )
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            with patch(
                "app.api.routes.search.get_hybrid_search_service",
                return_value=mock_search_service,
            ):
                token = create_test_token()
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/search",
                        json={"query": "test"},
                        headers={"Authorization": f"Bearer {token}"},
                    )

                assert response.status_code == 503
                data = response.json()
                assert data["error"]["code"] == "DATABASE_NOT_CONFIGURED"
        finally:
            app.dependency_overrides.clear()


class TestSearchMatterIsolation:
    """Tests for matter isolation in search endpoints."""

    @pytest.mark.anyio
    async def test_rejects_unauthorized_matter_access(self) -> None:
        """Should reject access to matters user doesn't belong to.

        Note: Returns 404 (not 403) to hide matter existence for security.
        """
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(None)  # No role = no access

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={"query": "test"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            # Returns 404 to hide matter existence (security best practice)
            assert response.status_code == 404
            data = response.json()
            assert data["error"]["code"] == "MATTER_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_validates_matter_id_format(self) -> None:
        """Should reject invalid UUID format for matter_id."""
        invalid_matter_id = "not-a-valid-uuid"

        app.dependency_overrides[get_settings] = get_test_settings
        # Even with valid role, invalid UUID should be rejected
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{invalid_matter_id}/search",
                    json={"query": "test"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            # Should fail at validation or access check level
            assert response.status_code in (400, 403, 422)
        finally:
            app.dependency_overrides.clear()
