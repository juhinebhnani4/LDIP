"""Tests for email notification Celery tasks.

Gap #19: Email Notification on Processing Completion - Task 8

Tests cover:
- send_processing_complete_notification task
- User opt-out behavior
- Error handling and resilience
"""

from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Create mock settings with email configuration."""
    settings = MagicMock()
    settings.email_notifications_enabled = True
    settings.resend_api_key = "test_api_key"
    settings.email_base_url = "https://test.ldip.com"
    return settings


@pytest.fixture
def mock_supabase_client():
    """Create mock Supabase client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_user_data():
    """Sample user data."""
    return {"id": "user-123", "email": "user@test.com"}


@pytest.fixture
def mock_preferences_opted_in():
    """User preferences with email notifications enabled."""
    return {"email_notifications_processing": True}


@pytest.fixture
def mock_preferences_opted_out():
    """User preferences with email notifications disabled."""
    return {"email_notifications_processing": False}


@pytest.fixture
def mock_matter_data():
    """Sample matter data."""
    return {"title": "Test Matter vs. Case"}


# =============================================================================
# Task Execution Tests
# =============================================================================


class TestSendProcessingCompleteNotification:
    """Tests for send_processing_complete_notification task."""

    def test_skipped_when_global_feature_disabled(self, mock_settings):
        """Test task skips when global email feature is disabled."""
        mock_settings.email_notifications_enabled = False

        with patch(
            "app.core.config.get_settings",
            return_value=mock_settings,
        ):
            from app.workers.tasks.email_tasks import send_processing_complete_notification

            result = send_processing_complete_notification(
                matter_id="matter-123",
                user_id="user-123",
                doc_count=10,
                success_count=8,
                failed_count=2,
            )

            assert result["status"] == "skipped"
            assert "disabled globally" in result["reason"]

    def test_skipped_when_resend_not_configured(self, mock_settings):
        """Test task skips when Resend API key is missing."""
        mock_settings.resend_api_key = ""

        with patch(
            "app.core.config.get_settings",
            return_value=mock_settings,
        ):
            from app.workers.tasks.email_tasks import send_processing_complete_notification

            result = send_processing_complete_notification(
                matter_id="matter-123",
                user_id="user-123",
                doc_count=10,
                success_count=10,
                failed_count=0,
            )

            assert result["status"] == "skipped"
            assert "not configured" in result["reason"]

    def test_skipped_when_user_opted_out(
        self,
        mock_settings,
        mock_supabase_client,
        mock_user_data,
        mock_preferences_opted_out,
        mock_matter_data,
    ):
        """Test task skips when user has opted out of email notifications."""
        # Setup mocks
        mock_auth_result = MagicMock()
        mock_auth_result.user = MagicMock()
        mock_auth_result.user.id = mock_user_data["id"]
        mock_auth_result.user.email = mock_user_data["email"]

        mock_supabase_client.auth.admin.get_user_by_id.return_value = mock_auth_result
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=mock_preferences_opted_out
        )

        with patch(
            "app.core.config.get_settings",
            return_value=mock_settings,
        ), patch(
            "app.services.supabase.client.get_service_client",
            return_value=mock_supabase_client,
        ):
            from app.workers.tasks.email_tasks import send_processing_complete_notification

            result = send_processing_complete_notification(
                matter_id="matter-123",
                user_id="user-123",
                doc_count=10,
                success_count=10,
                failed_count=0,
            )

            assert result["status"] == "skipped"
            assert "opted out" in result["reason"]

    def test_skipped_when_user_not_found(self, mock_settings, mock_supabase_client):
        """Test task skips when user is not found."""
        mock_auth_result = MagicMock()
        mock_auth_result.user = None
        mock_supabase_client.auth.admin.get_user_by_id.return_value = mock_auth_result

        with patch(
            "app.core.config.get_settings",
            return_value=mock_settings,
        ), patch(
            "app.services.supabase.client.get_service_client",
            return_value=mock_supabase_client,
        ):
            from app.workers.tasks.email_tasks import send_processing_complete_notification

            result = send_processing_complete_notification(
                matter_id="matter-123",
                user_id="user-123",
                doc_count=10,
                success_count=10,
                failed_count=0,
            )

            assert result["status"] == "skipped"
            assert "not found" in result["reason"]


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for email task helper functions."""

    def test_get_user_data_sync_success(self, mock_supabase_client, mock_user_data):
        """Test _get_user_data_sync returns user data."""
        from app.workers.tasks.email_tasks import _get_user_data_sync

        mock_auth_result = MagicMock()
        mock_auth_result.user = MagicMock()
        mock_auth_result.user.id = mock_user_data["id"]
        mock_auth_result.user.email = mock_user_data["email"]
        mock_supabase_client.auth.admin.get_user_by_id.return_value = mock_auth_result

        result = _get_user_data_sync(mock_supabase_client, "user-123")

        assert result is not None
        assert result["email"] == mock_user_data["email"]

    def test_get_user_data_sync_not_found(self, mock_supabase_client):
        """Test _get_user_data_sync returns None when user not found."""
        from app.workers.tasks.email_tasks import _get_user_data_sync

        mock_auth_result = MagicMock()
        mock_auth_result.user = None
        mock_supabase_client.auth.admin.get_user_by_id.return_value = mock_auth_result

        result = _get_user_data_sync(mock_supabase_client, "user-123")

        assert result is None

    def test_get_user_preferences_sync_success(
        self, mock_supabase_client, mock_preferences_opted_in
    ):
        """Test _get_user_preferences_sync returns preferences."""
        from app.workers.tasks.email_tasks import _get_user_preferences_sync

        mock_result = MagicMock()
        mock_result.data = mock_preferences_opted_in
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_result

        result = _get_user_preferences_sync(mock_supabase_client, "user-123")

        assert result is not None
        assert result["email_notifications_processing"] is True

    def test_get_matter_data_sync_success(
        self, mock_supabase_client, mock_matter_data
    ):
        """Test _get_matter_data_sync returns matter data."""
        from app.workers.tasks.email_tasks import _get_matter_data_sync

        mock_result = MagicMock()
        mock_result.data = mock_matter_data
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_result

        result = _get_matter_data_sync(mock_supabase_client, "matter-123")

        assert result is not None
        assert result["title"] == mock_matter_data["title"]
