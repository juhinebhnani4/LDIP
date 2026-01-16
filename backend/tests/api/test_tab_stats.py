"""Unit tests for tab stats API endpoint.

Story 14.12: Tab Stats API (Task 5)

Tests for GET /api/matters/{matter_id}/tab-stats endpoint.
Uses FastAPI dependency_overrides pattern for proper test isolation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_tab_stats_service_dep
from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.main import app
from app.models.matter import MatterRole
from app.models.tab_stats import (
    TabCountsData,
    TabProcessingStatusData,
    TabStats,
    TabStatsData,
)
from app.services.tab_stats_service import (
    TabStatsService,
    TabStatsServiceError,
)


# Disable rate limiting for tests
@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for all tests in this module."""
    limiter.enabled = False
    yield
    limiter.enabled = True


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


def create_mock_tab_stats_data() -> TabStatsData:
    """Create mock tab stats data for testing."""
    return TabStatsData(
        tab_counts=TabCountsData(
            summary=TabStats(count=1, issue_count=0),
            timeline=TabStats(count=24, issue_count=0),
            entities=TabStats(count=18, issue_count=2),
            citations=TabStats(count=45, issue_count=3),
            contradictions=TabStats(count=7, issue_count=7),
            verification=TabStats(count=12, issue_count=5),
            documents=TabStats(count=8, issue_count=0),
        ),
        tab_processing_status=TabProcessingStatusData(
            summary="ready",
            timeline="ready",
            entities="processing",
            citations="ready",
            contradictions="ready",
            verification="ready",
            documents="ready",
        ),
    )


class TestGetTabStats:
    """Tests for GET /api/matters/{matter_id}/tab-stats endpoint."""

    @pytest.mark.anyio
    async def test_returns_tab_stats_for_authenticated_user(self) -> None:
        """Should return tab statistics for authenticated user with matter access."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_stats = create_mock_tab_stats_data()

        mock_service = AsyncMock(spec=TabStatsService)
        mock_service.get_tab_stats.return_value = mock_stats

        # Mock matter membership check - return actual MatterRole enum
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        from app.api.deps import get_matter_service

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tab_stats_service_dep] = lambda: mock_service
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/tab-stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "tabCounts" in data["data"]
            assert "tabProcessingStatus" in data["data"]

            # Verify tab counts structure
            tab_counts = data["data"]["tabCounts"]
            assert tab_counts["summary"]["count"] == 1
            assert tab_counts["timeline"]["count"] == 24
            assert tab_counts["entities"]["count"] == 18
            assert tab_counts["entities"]["issueCount"] == 2
            assert tab_counts["citations"]["count"] == 45
            assert tab_counts["citations"]["issueCount"] == 3
            assert tab_counts["contradictions"]["count"] == 7
            assert tab_counts["verification"]["count"] == 12
            assert tab_counts["documents"]["count"] == 8

            # Verify processing status
            processing_status = data["data"]["tabProcessingStatus"]
            assert processing_status["summary"] == "ready"
            assert processing_status["entities"] == "processing"
            assert processing_status["timeline"] == "ready"

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_zero_counts_for_empty_matter(self) -> None:
        """Should return zero counts for matter with no data."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_stats = TabStatsData(
            tab_counts=TabCountsData(
                summary=TabStats(count=1, issue_count=0),
                timeline=TabStats(count=0, issue_count=0),
                entities=TabStats(count=0, issue_count=0),
                citations=TabStats(count=0, issue_count=0),
                contradictions=TabStats(count=0, issue_count=0),
                verification=TabStats(count=0, issue_count=0),
                documents=TabStats(count=0, issue_count=0),
            ),
            tab_processing_status=TabProcessingStatusData(),
        )

        mock_service = AsyncMock(spec=TabStatsService)
        mock_service.get_tab_stats.return_value = mock_stats

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        from app.api.deps import get_matter_service

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tab_stats_service_dep] = lambda: mock_service
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/tab-stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["tabCounts"]["timeline"]["count"] == 0
            assert data["data"]["tabCounts"]["entities"]["count"] == 0
            assert data["data"]["tabCounts"]["documents"]["count"] == 0

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_rejects_unauthenticated_request(self) -> None:
        """Should return 401 for unauthenticated requests."""
        matter_id = str(uuid4())

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/matters/{matter_id}/tab-stats")

            assert response.status_code == 401

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_404_for_non_member(self) -> None:
        """Should return 404 for user without matter access."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = None  # No role = no access

        from app.api.deps import get_matter_service

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/tab-stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 404
            data = response.json()
            assert data["error"]["code"] == "MATTER_NOT_FOUND"

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_handles_service_error_gracefully(self) -> None:
        """Should return 500 on service error."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_service = AsyncMock(spec=TabStatsService)
        mock_service.get_tab_stats.side_effect = TabStatsServiceError(
            "Database error",
            code="DB_ERROR",
            status_code=500,
        )

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        from app.api.deps import get_matter_service

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tab_stats_service_dep] = lambda: mock_service
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/tab-stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 500
            data = response.json()
            assert data["error"]["code"] == "DB_ERROR"

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_viewer_can_access_tab_stats(self) -> None:
        """Should allow viewer role to access tab stats."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_stats = create_mock_tab_stats_data()

        mock_service = AsyncMock(spec=TabStatsService)
        mock_service.get_tab_stats.return_value = mock_stats

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        from app.api.deps import get_matter_service

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tab_stats_service_dep] = lambda: mock_service
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/tab-stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_editor_can_access_tab_stats(self) -> None:
        """Should allow editor role to access tab stats."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_stats = create_mock_tab_stats_data()

        mock_service = AsyncMock(spec=TabStatsService)
        mock_service.get_tab_stats.return_value = mock_stats

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        from app.api.deps import get_matter_service

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tab_stats_service_dep] = lambda: mock_service
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/tab-stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_processing_status_detection(self) -> None:
        """Should correctly return processing status when jobs are active."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        # Mock with multiple tabs processing
        mock_stats = TabStatsData(
            tab_counts=TabCountsData(
                summary=TabStats(count=1, issue_count=0),
                timeline=TabStats(count=10, issue_count=0),
                entities=TabStats(count=5, issue_count=1),
                citations=TabStats(count=20, issue_count=2),
                contradictions=TabStats(count=3, issue_count=3),
                verification=TabStats(count=0, issue_count=0),
                documents=TabStats(count=4, issue_count=0),
            ),
            tab_processing_status=TabProcessingStatusData(
                summary="ready",
                timeline="processing",  # Date extraction running
                entities="processing",  # Entity extraction running
                citations="ready",
                contradictions="ready",
                verification="ready",
                documents="processing",  # OCR running
            ),
        )

        mock_service = AsyncMock(spec=TabStatsService)
        mock_service.get_tab_stats.return_value = mock_stats

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        from app.api.deps import get_matter_service

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tab_stats_service_dep] = lambda: mock_service
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/tab-stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()

            status = data["data"]["tabProcessingStatus"]
            assert status["timeline"] == "processing"
            assert status["entities"] == "processing"
            assert status["documents"] == "processing"
            assert status["summary"] == "ready"
            assert status["citations"] == "ready"

        finally:
            app.dependency_overrides.clear()
