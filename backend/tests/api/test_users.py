"""
Tests for user management API routes.

Story 14.14: Settings Page Implementation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models.auth import AuthenticatedUser


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return AuthenticatedUser(
        id="test-user-id",
        email="test@example.com",
        role="user",
    )


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def client(mock_user, mock_supabase):
    """Create a test client with mocked dependencies."""
    from app.api.routes import users

    # Override dependencies
    app.dependency_overrides[users.get_supabase_client] = lambda: mock_supabase

    with patch("app.core.security.get_current_user", return_value=mock_user):
        with TestClient(app) as test_client:
            yield test_client

    # Clean up
    app.dependency_overrides.clear()


# =============================================================================
# GET /api/users/me/preferences Tests
# =============================================================================


class TestGetUserPreferences:
    """Tests for GET /api/users/me/preferences endpoint."""

    def test_get_preferences_success(self, client, mock_supabase):
        """Should return user preferences."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "user_id": "test-user-id",
            "email_notifications_processing": True,
            "email_notifications_verification": True,
            "browser_notifications": False,
            "theme": "system",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        response = client.get("/api/users/me/preferences")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email_notifications_processing"] is True
        assert data["email_notifications_verification"] is True
        assert data["browser_notifications"] is False
        assert data["theme"] == "system"

    def test_get_preferences_creates_default_if_not_exists(self, client, mock_supabase):
        """Should create default preferences if they don't exist."""
        # First call returns empty (no preferences)
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()

        # Second call returns the created preferences
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "user_id": "test-user-id",
            "email_notifications_processing": True,
            "email_notifications_verification": True,
            "browser_notifications": False,
            "theme": "system",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        response = client.get("/api/users/me/preferences")

        assert response.status_code == status.HTTP_200_OK
        # Verify insert was called
        mock_supabase.table.return_value.insert.assert_called()

    def test_get_preferences_unauthorized(self):
        """Should return 401 for unauthorized requests."""
        with TestClient(app) as client:
            response = client.get("/api/users/me/preferences")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# PATCH /api/users/me/preferences Tests
# =============================================================================


class TestUpdateUserPreferences:
    """Tests for PATCH /api/users/me/preferences endpoint."""

    def test_update_preferences_success(self, client, mock_supabase):
        """Should update user preferences."""
        # Setup mocks
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"user_id": "test-user-id"}
        ]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {
                "user_id": "test-user-id",
                "email_notifications_processing": False,
                "email_notifications_verification": True,
                "browser_notifications": False,
                "theme": "dark",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]

        response = client.patch(
            "/api/users/me/preferences",
            json={"email_notifications_processing": False, "theme": "dark"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email_notifications_processing"] is False
        assert data["theme"] == "dark"

    def test_update_preferences_partial(self, client, mock_supabase):
        """Should allow partial updates."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"user_id": "test-user-id"}
        ]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {
                "user_id": "test-user-id",
                "email_notifications_processing": True,
                "email_notifications_verification": True,
                "browser_notifications": True,
                "theme": "system",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]

        # Only update one field
        response = client.patch(
            "/api/users/me/preferences",
            json={"browser_notifications": True},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["browser_notifications"] is True

    def test_update_preferences_invalid_theme(self, client):
        """Should reject invalid theme values."""
        response = client.patch(
            "/api/users/me/preferences",
            json={"theme": "invalid-theme"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# GET /api/users/me/profile Tests
# =============================================================================


class TestGetUserProfile:
    """Tests for GET /api/users/me/profile endpoint."""

    def test_get_profile_success(self, client, mock_user):
        """Should return user profile."""
        response = client.get("/api/users/me/profile")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "test-user-id"
        assert data["email"] == "test@example.com"


# =============================================================================
# PATCH /api/users/me/profile Tests
# =============================================================================


class TestUpdateUserProfile:
    """Tests for PATCH /api/users/me/profile endpoint."""

    def test_update_profile_success(self, client, mock_supabase):
        """Should update user profile."""
        mock_user_result = MagicMock()
        mock_user_result.id = "test-user-id"
        mock_user_result.email = "test@example.com"
        mock_user_result.user_metadata = {
            "full_name": "New Name",
            "avatar_url": None,
        }
        mock_supabase.auth.admin.update_user_by_id.return_value.user = mock_user_result

        response = client.patch(
            "/api/users/me/profile",
            json={"full_name": "New Name"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["full_name"] == "New Name"

    def test_update_profile_name_too_long(self, client):
        """Should reject names that are too long."""
        response = client.patch(
            "/api/users/me/profile",
            json={"full_name": "A" * 101},  # Exceeds 100 char limit
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_profile_empty_body(self, client, mock_user):
        """Should handle empty update body."""
        response = client.patch(
            "/api/users/me/profile",
            json={},
        )

        # Should return current profile without changes
        assert response.status_code == status.HTTP_200_OK
