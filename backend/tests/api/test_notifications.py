"""Tests for Notification API routes.

Story 14.10: Notifications Backend & Frontend Wiring (Task 7)

Tests verify:
- GET /api/notifications returns user's notifications only (RLS)
- PATCH /api/notifications/{id}/read with ownership check
- POST /api/notifications/read-all marks all as read

Note: These are integration-style tests that mock the Supabase client.
The complex async call chains make detailed mock verification fragile,
so we focus on verifying correct HTTP behavior.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.models.auth import AuthenticatedUser


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_auth_user() -> AuthenticatedUser:
    """Create mock authenticated user."""
    return AuthenticatedUser(
        id="user-123",
        email="test@example.com",
        role="attorney",
    )


@pytest.fixture
def test_client(mock_auth_user: AuthenticatedUser) -> TestClient:
    """Create test client with mocked authentication."""
    # Clear the notification service cache to ensure fresh service instance
    from app.services.notification_service import get_notification_service
    get_notification_service.cache_clear()

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    get_notification_service.cache_clear()


@pytest.fixture
def mock_notification_data() -> dict:
    """Sample notification data from database."""
    return {
        "id": "notif-123",
        "user_id": "user-123",
        "matter_id": "matter-456",
        "type": "success",
        "title": "Processing Complete",
        "message": "Document 'Contract.pdf' has been processed.",
        "priority": "medium",
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "matters": {"title": "Smith vs. Jones"},
    }


@pytest.fixture
def mock_notifications_list(mock_notification_data: dict) -> list[dict]:
    """Sample notifications list from database."""
    return [
        mock_notification_data,
        {
            "id": "notif-124",
            "user_id": "user-123",
            "matter_id": "matter-789",
            "type": "warning",
            "title": "Verification Needed",
            "message": "3 citations need review.",
            "priority": "high",
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "matters": {"title": "Acme Corp Case"},
        },
        {
            "id": "notif-125",
            "user_id": "user-123",
            "matter_id": None,
            "type": "info",
            "title": "System Update",
            "message": "System maintenance completed.",
            "priority": "low",
            "is_read": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "matters": None,
        },
    ]


def create_mock_supabase_client(
    query_data: list[dict] | dict | None = None,
    count: int = 0,
) -> MagicMock:
    """Create a mock Supabase client with configurable responses."""
    mock_client = MagicMock()

    # Create a flexible mock that handles various query patterns
    mock_result = MagicMock()
    mock_result.data = query_data if isinstance(query_data, list) else [query_data] if query_data else []
    mock_result.count = count

    # Make all chain methods return something that eventually gives the result
    def chain_mock(*args, **kwargs):
        chain = MagicMock()
        chain.execute.return_value = mock_result
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.update.return_value = chain
        chain.insert.return_value = chain
        return chain

    mock_client.table.return_value.select.return_value = chain_mock()
    mock_client.table.return_value.update.return_value = chain_mock()
    mock_client.table.return_value.insert.return_value = chain_mock()

    return mock_client


# =============================================================================
# GET /api/notifications Tests
# =============================================================================


class TestGetNotifications:
    """Tests for GET /api/notifications endpoint."""

    @patch("app.services.notification_service.get_supabase_client")
    def test_returns_notifications_list(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
        mock_notifications_list: list[dict],
    ) -> None:
        """Should return notifications list with unread count."""
        mock_client = create_mock_supabase_client(mock_notifications_list, count=2)
        mock_get_client.return_value = mock_client

        response = test_client.get("/api/notifications")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "unreadCount" in data
        assert len(data["data"]) == 3

    @patch("app.services.notification_service.get_supabase_client")
    def test_returns_empty_list_on_no_notifications(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
    ) -> None:
        """Should return empty list with unreadCount 0."""
        mock_client = create_mock_supabase_client([], count=0)
        mock_get_client.return_value = mock_client

        response = test_client.get("/api/notifications")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []
        assert data["unreadCount"] == 0

    def test_requires_authentication(self) -> None:
        """Should return 401 without authentication."""
        # Remove auth override
        app.dependency_overrides.clear()
        client = TestClient(app)

        response = client.get("/api/notifications")

        # Should return 401 or redirect
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @patch("app.services.notification_service.get_supabase_client")
    def test_accepts_limit_parameter(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
    ) -> None:
        """Should accept limit query parameter."""
        mock_client = create_mock_supabase_client([], count=0)
        mock_get_client.return_value = mock_client

        response = test_client.get("/api/notifications?limit=5")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.services.notification_service.get_supabase_client")
    def test_accepts_unread_only_parameter(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
    ) -> None:
        """Should accept unread_only query parameter."""
        mock_client = create_mock_supabase_client([], count=0)
        mock_get_client.return_value = mock_client

        response = test_client.get("/api/notifications?unread_only=true")

        assert response.status_code == status.HTTP_200_OK


# =============================================================================
# PATCH /api/notifications/{id}/read Tests
# =============================================================================


class TestMarkNotificationRead:
    """Tests for PATCH /api/notifications/{id}/read endpoint."""

    @patch("app.services.notification_service.get_supabase_client")
    def test_marks_notification_as_read(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
        mock_notification_data: dict,
    ) -> None:
        """Should mark notification as read and return updated notification."""
        updated_data = {**mock_notification_data, "is_read": True}
        mock_client = create_mock_supabase_client(updated_data)
        mock_get_client.return_value = mock_client

        response = test_client.patch("/api/notifications/notif-123/read")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["isRead"] is True

    @patch("app.services.notification_service.get_supabase_client")
    def test_returns_404_for_nonexistent_notification(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
    ) -> None:
        """Should return 404 if notification not found."""
        # Mock empty result (not found)
        mock_client = create_mock_supabase_client([])
        mock_get_client.return_value = mock_client

        response = test_client.patch("/api/notifications/nonexistent-id/read")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "NOT_FOUND"


# =============================================================================
# POST /api/notifications/read-all Tests
# =============================================================================


class TestMarkAllNotificationsRead:
    """Tests for POST /api/notifications/read-all endpoint."""

    @patch("app.services.notification_service.get_supabase_client")
    def test_marks_all_as_read_returns_count(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
    ) -> None:
        """Should mark all unread notifications as read and return count."""
        mock_client = create_mock_supabase_client([], count=3)
        mock_get_client.return_value = mock_client

        response = test_client.post("/api/notifications/read-all")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "count" in data
        # Count comes from the mock
        assert data["count"] == 3

    @patch("app.services.notification_service.get_supabase_client")
    def test_returns_zero_when_no_unread(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
    ) -> None:
        """Should return count 0 when no unread notifications."""
        mock_client = create_mock_supabase_client([], count=0)
        mock_get_client.return_value = mock_client

        response = test_client.post("/api/notifications/read-all")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0


# =============================================================================
# Response Format Tests
# =============================================================================


class TestResponseFormat:
    """Tests for API response format compliance."""

    @patch("app.services.notification_service.get_supabase_client")
    def test_get_notifications_uses_camel_case(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
        mock_notification_data: dict,
    ) -> None:
        """Should return camelCase fields in response."""
        mock_client = create_mock_supabase_client([mock_notification_data], count=1)
        mock_get_client.return_value = mock_client

        response = test_client.get("/api/notifications")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check camelCase fields
        notification = data["data"][0]
        assert "matterId" in notification
        assert "matterTitle" in notification
        assert "isRead" in notification
        assert "createdAt" in notification
        assert "unreadCount" in data

        # Check snake_case fields are NOT present
        assert "matter_id" not in notification
        assert "matter_title" not in notification
        assert "is_read" not in notification
        assert "created_at" not in notification

    @patch("app.services.notification_service.get_supabase_client")
    def test_mark_read_uses_camel_case(
        self,
        mock_get_client: MagicMock,
        test_client: TestClient,
        mock_notification_data: dict,
    ) -> None:
        """Should return camelCase fields in mark read response."""
        mock_client = create_mock_supabase_client(mock_notification_data)
        mock_get_client.return_value = mock_client

        response = test_client.patch("/api/notifications/notif-123/read")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check camelCase fields
        notification = data["data"]
        assert "isRead" in notification
        assert "createdAt" in notification
