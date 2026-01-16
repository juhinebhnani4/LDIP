"""Unit tests for activity API routes.

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
from app.models.activity import ActivityTypeEnum, ActivityRecord
from app.services.activity_service import ActivityServiceError


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


def create_mock_activity(
    activity_id: str | None = None,
    matter_id: str | None = None,
    activity_type: ActivityTypeEnum = ActivityTypeEnum.PROCESSING_COMPLETE,
    description: str = "Test activity",
    is_read: bool = False,
) -> ActivityRecord:
    """Create a mock ActivityRecord for testing."""
    return ActivityRecord(
        id=activity_id or str(uuid4()),
        matter_id=matter_id,
        matter_name="Test Matter" if matter_id else None,
        type=activity_type,
        description=description,
        timestamp=datetime.now(timezone.utc),
        is_read=is_read,
    )


class TestGetActivities:
    """Tests for GET /api/activity-feed endpoint."""

    @pytest.mark.asyncio
    async def test_returns_activities_list(self) -> None:
        """Should return activities for authenticated user."""
        user_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_activities = [
            create_mock_activity(
                matter_id=str(uuid4()),
                activity_type=ActivityTypeEnum.PROCESSING_COMPLETE,
            ),
            create_mock_activity(
                matter_id=str(uuid4()),
                activity_type=ActivityTypeEnum.PROCESSING_STARTED,
            ),
        ]

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.activity_service.get_activity_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.get_activities.return_value = (mock_activities, 2)
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/activity-feed",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["meta"]["total"] == 2

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self) -> None:
        """Should pass limit parameter to service."""
        user_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.activity_service.get_activity_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.get_activities.return_value = ([], 0)
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.get(
                    "/api/activity-feed?limit=5",
                    headers={"Authorization": f"Bearer {token}"},
                )

        mock_service.get_activities.assert_called_once()
        call_args = mock_service.get_activities.call_args
        assert call_args.kwargs["limit"] == 5

    @pytest.mark.asyncio
    async def test_respects_matter_id_filter(self) -> None:
        """Should pass matterId filter to service."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.activity_service.get_activity_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.get_activities.return_value = ([], 0)
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.get(
                    f"/api/activity-feed?matterId={matter_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

        mock_service.get_activities.assert_called_once()
        call_args = mock_service.get_activities.call_args
        assert call_args.kwargs["matter_id"] == matter_id

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated_request(self) -> None:
        """Should return 401 for unauthenticated requests."""
        with patch(
            "app.core.config.get_settings", return_value=get_test_settings()
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/activity-feed")

        assert response.status_code == 401


class TestMarkActivityRead:
    """Tests for PATCH /api/activity-feed/{id}/read endpoint."""

    @pytest.mark.asyncio
    async def test_marks_activity_as_read(self) -> None:
        """Should mark activity as read and return updated activity."""
        user_id = str(uuid4())
        activity_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        mock_activity = create_mock_activity(
            activity_id=activity_id,
            matter_id=str(uuid4()),
            is_read=True,
        )

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.activity_service.get_activity_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.mark_as_read.return_value = mock_activity
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch(
                    f"/api/activity-feed/{activity_id}/read",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == activity_id
        assert data["data"]["isRead"] is True

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_activity(self) -> None:
        """Should return 404 when activity not found."""
        user_id = str(uuid4())
        activity_id = str(uuid4())
        token = create_test_token(user_id=user_id)

        with (
            patch(
                "app.core.config.get_settings", return_value=get_test_settings()
            ),
            patch(
                "app.services.activity_service.get_activity_service"
            ) as mock_get_service,
        ):
            mock_service = AsyncMock()
            mock_service.mark_as_read.return_value = None
            mock_get_service.return_value = mock_service

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch(
                    f"/api/activity-feed/{activity_id}/read",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated_request(self) -> None:
        """Should return 401 for unauthenticated requests."""
        activity_id = str(uuid4())

        with patch(
            "app.core.config.get_settings", return_value=get_test_settings()
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch(
                    f"/api/activity-feed/{activity_id}/read"
                )

        assert response.status_code == 401
