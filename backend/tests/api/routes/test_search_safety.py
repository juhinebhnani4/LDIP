"""Tests for search API route safety integration.

Story 8-1/8-2 Code Review Fix: Tests for SafetyGuard integration
in search endpoints to prevent bypassing guardrails via search queries.

Tests verify:
- Unsafe queries are blocked with 400 SAFETY_VIOLATION response
- Safe queries proceed to search execution
- All search endpoints (hybrid, bm25, semantic, rerank, alias-expanded) are protected
"""

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
from app.models.safety import SafetyCheckResult
from app.services.rag.hybrid_search import (
    HybridSearchResult,
    SearchResult,
    SearchWeights,
)
from app.services.safety import get_safety_guard

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


def create_mock_search_result(matter_id: str) -> SearchResult:
    """Create a mock search result for testing."""
    return SearchResult(
        id=str(uuid4()),
        matter_id=matter_id,
        document_id=str(uuid4()),
        content="Test legal content about contract termination.",
        page_number=5,
        chunk_type="child",
        token_count=150,
        bm25_rank=1,
        semantic_rank=2,
        rrf_score=0.032,
    )


def create_mock_matter_service(role: MatterRole | None = MatterRole.VIEWER) -> MagicMock:
    """Create a mock matter service for testing."""
    mock_service = MagicMock()
    mock_service.get_user_role.return_value = role
    return mock_service


def create_mock_safety_guard_safe() -> MagicMock:
    """Create a mock safety guard that allows queries."""
    mock_guard = MagicMock()
    mock_guard.check_query = AsyncMock(
        return_value=SafetyCheckResult(
            is_safe=True,
            blocked_by=None,
            regex_check_ms=2.0,
        )
    )
    return mock_guard


def create_mock_safety_guard_unsafe_regex() -> MagicMock:
    """Create a mock safety guard that blocks queries (regex)."""
    mock_guard = MagicMock()
    mock_guard.check_query = AsyncMock(
        return_value=SafetyCheckResult(
            is_safe=False,
            blocked_by="regex",
            violation_type="legal_advice_request",
            explanation="This query seeks legal advice which is not permitted.",
            suggested_rewrite="What does the document say about...",
            regex_check_ms=2.5,
        )
    )
    return mock_guard


def create_mock_safety_guard_unsafe_llm() -> MagicMock:
    """Create a mock safety guard that blocks queries (LLM)."""
    mock_guard = MagicMock()
    mock_guard.check_query = AsyncMock(
        return_value=SafetyCheckResult(
            is_safe=False,
            blocked_by="llm",
            violation_type="implicit_conclusion_request",
            explanation="Query seeks implicit legal conclusion.",
            suggested_rewrite="What evidence exists regarding...",
            regex_check_ms=2.0,
            llm_check_ms=850.0,
            llm_cost_usd=0.0003,
        )
    )
    return mock_guard


# =============================================================================
# Story 8-1/8-2: Search Safety Tests
# =============================================================================


class TestSearchSafetyHybrid:
    """Tests for safety guard integration in hybrid search endpoint."""

    @pytest.mark.anyio
    async def test_blocks_unsafe_query_regex(self) -> None:
        """Should return 400 SAFETY_VIOLATION when regex blocks query."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_regex

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={"query": "Should I file an appeal?"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "SAFETY_VIOLATION"
            assert "violation_type" in data["detail"]["error"]["details"]
            assert data["detail"]["error"]["details"]["violation_type"] == "legal_advice_request"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_blocks_unsafe_query_llm(self) -> None:
        """Should return 400 SAFETY_VIOLATION when LLM blocks query."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_llm

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={"query": "Based on this evidence, is it clear that..."},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "SAFETY_VIOLATION"
            assert data["detail"]["error"]["details"]["violation_type"] == "implicit_conclusion_request"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_allows_safe_query(self) -> None:
        """Should allow safe query through to search execution."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        mock_search_service = MagicMock()
        mock_result = HybridSearchResult(
            query="contract termination",
            matter_id=matter_id,
            results=[create_mock_search_result(matter_id)],
            total_candidates=10,
            weights=SearchWeights(bm25=1.0, semantic=1.0),
        )
        mock_search_service.search = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_safe

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
                        json={"query": "contract termination"},
                        headers={"Authorization": f"Bearer {token}"},
                    )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 1
        finally:
            app.dependency_overrides.clear()


class TestSearchSafetyBM25:
    """Tests for safety guard integration in BM25 search endpoint."""

    @pytest.mark.anyio
    async def test_blocks_unsafe_query(self) -> None:
        """Should return 400 SAFETY_VIOLATION when safety blocks query."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_regex

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search/bm25",
                    json={"query": "how to hide assets"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "SAFETY_VIOLATION"
        finally:
            app.dependency_overrides.clear()


class TestSearchSafetySemantic:
    """Tests for safety guard integration in semantic search endpoint."""

    @pytest.mark.anyio
    async def test_blocks_unsafe_query(self) -> None:
        """Should return 400 SAFETY_VIOLATION when safety blocks query."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_regex

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search/semantic",
                    json={"query": "what should I do about this case"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "SAFETY_VIOLATION"
        finally:
            app.dependency_overrides.clear()


class TestSearchSafetyRerank:
    """Tests for safety guard integration in rerank search endpoint."""

    @pytest.mark.anyio
    async def test_blocks_unsafe_query(self) -> None:
        """Should return 400 SAFETY_VIOLATION when safety blocks query."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_regex

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search/rerank",
                    json={"query": "am I liable for this", "limit": 20, "top_n": 3},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "SAFETY_VIOLATION"
        finally:
            app.dependency_overrides.clear()


class TestSearchSafetyAliasExpanded:
    """Tests for safety guard integration in alias-expanded search endpoint."""

    @pytest.mark.anyio
    async def test_blocks_unsafe_query(self) -> None:
        """Should return 400 SAFETY_VIOLATION when safety blocks query."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_regex

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search/alias-expanded",
                    json={"query": "give me legal advice about N.D. Jobalia"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "SAFETY_VIOLATION"
        finally:
            app.dependency_overrides.clear()


class TestSearchSafetyResponseFormat:
    """Tests for correct safety violation response format."""

    @pytest.mark.anyio
    async def test_response_includes_suggested_rewrite(self) -> None:
        """Should include suggested_rewrite in safety violation response."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_regex

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={"query": "Should I file an appeal?"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            details = data["detail"]["error"]["details"]
            assert "suggested_rewrite" in details
            assert details["suggested_rewrite"] == "What does the document say about..."
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_response_includes_violation_type(self) -> None:
        """Should include violation_type in safety violation response."""
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[get_safety_guard] = create_mock_safety_guard_unsafe_llm

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/search",
                    json={"query": "is this evidence conclusive"},
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 400
            data = response.json()
            details = data["detail"]["error"]["details"]
            assert details["violation_type"] == "implicit_conclusion_request"
        finally:
            app.dependency_overrides.clear()
