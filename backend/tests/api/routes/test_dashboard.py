"""Unit tests for dashboard API routes.

Story 14.5: Dashboard Real APIs
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.activity import DashboardStats
from app.services.dashboard_stats_service import DashboardStatsServiceError


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


class TestGetDashboardStats:
    """Tests for GET /api/dashboard/stats endpoint."""

    @pytest.mark.asyncio
    async def test_returns_dashboard_stats(self) -> None:
        """Should return dashboard statistics for authenticated user."""
        user_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_stats = DashboardStats(
            active_matters=5,
            verified_findings=127,
            pending_reviews=3,
        )

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.dashboard_stats_service.get_dashboard_stats_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.get_dashboard_stats.return_value = mock_stats
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/dashboard/stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"]["activeMatters"] == 5
        assert data["data"]["verifiedFindings"] == 127
        assert data["data"]["pendingReviews"] == 3

    @pytest.mark.asyncio
    async def test_returns_zero_stats_for_new_user(self) -> None:
        """Should return zero stats for user with no data."""
        user_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_stats = DashboardStats(
            active_matters=0,
            verified_findings=0,
            pending_reviews=0,
        )

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.dashboard_stats_service.get_dashboard_stats_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.get_dashboard_stats.return_value = mock_stats
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/dashboard/stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["activeMatters"] == 0
        assert data["data"]["verifiedFindings"] == 0
        assert data["data"]["pendingReviews"] == 0

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated_request(self) -> None:
        """Should return 401 for unauthenticated requests."""
        with patch(
            "app.core.config.get_settings", return_value=get_test_settings()
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/dashboard/stats")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_handles_service_error_gracefully(self) -> None:
        """Should return 500 on service error."""
        user_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.dashboard_stats_service.get_dashboard_stats_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.get_dashboard_stats.side_effect = DashboardStatsServiceError(
                "Database error",
                code="DB_ERROR",
                status_code=500,
            )
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/dashboard/stats",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"]["code"] == "DB_ERROR"
