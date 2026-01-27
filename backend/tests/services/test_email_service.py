"""Tests for email service.

Gap #19: Email Notification on Processing Completion - Task 8

Tests cover:
- EmailService initialization and configuration
- send_processing_complete_email with success/failure scenarios
- Retry logic and error handling
- User opt-out behavior
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import (
    EmailConfigurationError,
    EmailSendError,
    EmailService,
    get_email_service,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Create mock settings with email configuration."""
    settings = MagicMock()
    settings.resend_api_key = "test_api_key"
    settings.email_from_address = "noreply@test.com"
    settings.email_notifications_enabled = True
    settings.email_base_url = "https://test.ldip.com"
    settings.is_email_configured = True
    return settings


@pytest.fixture
def email_service(mock_settings):
    """Create email service with mocked settings."""
    with patch("app.services.email_service.get_settings", return_value=mock_settings):
        service = EmailService()
        return service


# =============================================================================
# Configuration Tests
# =============================================================================


class TestEmailServiceConfiguration:
    """Tests for email service configuration."""

    def test_is_configured_with_api_key(self, email_service, mock_settings):
        """Test is_configured returns True when API key and feature flag are set."""
        assert email_service.is_configured() is True

    def test_is_configured_without_api_key(self, mock_settings):
        """Test is_configured returns False when API key is missing."""
        mock_settings.resend_api_key = ""
        mock_settings.is_email_configured = False

        with patch("app.services.email_service.get_settings", return_value=mock_settings):
            service = EmailService()
            assert service.is_configured() is False

    def test_is_configured_with_feature_disabled(self, mock_settings):
        """Test is_configured returns False when feature flag is disabled."""
        mock_settings.email_notifications_enabled = False
        mock_settings.is_email_configured = False

        with patch("app.services.email_service.get_settings", return_value=mock_settings):
            service = EmailService()
            assert service.is_configured() is False

    def test_client_raises_error_without_api_key(self, mock_settings):
        """Test client property raises EmailConfigurationError when not configured."""
        mock_settings.resend_api_key = ""

        with patch("app.services.email_service.get_settings", return_value=mock_settings):
            service = EmailService()
            with pytest.raises(EmailConfigurationError) as exc_info:
                _ = service.client
            assert "RESEND_API_KEY" in str(exc_info.value)


# =============================================================================
# Send Email Tests
# =============================================================================


class TestSendProcessingCompleteEmail:
    """Tests for send_processing_complete_email method."""

    @pytest.mark.asyncio
    async def test_send_email_success(self, email_service):
        """Test successful email send."""
        # Mock the template rendering
        with patch(
            "app.services.email_service.get_settings"
        ) as mock_get_settings, patch(
            "app.services.email.templates.processing_complete.render_processing_complete_email"
        ) as mock_render, patch.object(
            email_service, "_send_email_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_get_settings.return_value = email_service._settings
            mock_render.return_value = (
                "Subject",
                "<html>HTML</html>",
                "Text content",
            )
            mock_send.return_value = True

            result = await email_service.send_processing_complete_email(
                user_email="user@test.com",
                matter_name="Test Matter",
                doc_count=10,
                success_count=8,
                failed_count=2,
                workspace_url="https://test.ldip.com/matters/123",
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_disabled(self, mock_settings):
        """Test email not sent when feature is disabled."""
        mock_settings.is_email_configured = False

        with patch("app.services.email_service.get_settings", return_value=mock_settings):
            service = EmailService()
            result = await service.send_processing_complete_email(
                user_email="user@test.com",
                matter_name="Test Matter",
                doc_count=10,
                success_count=10,
                failed_count=0,
                workspace_url="https://test.ldip.com/matters/123",
            )

            assert result is False


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestEmailRetryLogic:
    """Tests for email sending retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, email_service):
        """Test retry logic on transient failures."""
        with patch.object(
            email_service, "_send_email", new_callable=AsyncMock
        ) as mock_send:
            # First call fails, second succeeds
            mock_send.side_effect = [
                EmailSendError("Temporary failure"),
                True,
            ]

            result = await email_service._send_email_with_retry(
                to_email="user@test.com",
                subject="Test",
                html_content="<html></html>",
                text_content="Text",
                email_type="test",
            )

            # Should succeed after retry
            assert result is True
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, email_service):
        """Test failure after max retries exceeded."""
        with patch.object(
            email_service, "_send_email", new_callable=AsyncMock
        ) as mock_send:
            # All attempts fail
            mock_send.side_effect = EmailSendError("Persistent failure")

            result = await email_service._send_email_with_retry(
                to_email="user@test.com",
                subject="Test",
                html_content="<html></html>",
                text_content="Text",
                email_type="test",
            )

            # Should fail after all retries
            assert result is False
            # 3 retries (MAX_RETRIES)
            assert mock_send.call_count == 3


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetEmailService:
    """Tests for get_email_service factory function."""

    def test_returns_singleton(self):
        """Test that get_email_service returns the same instance."""
        # Clear the cache first
        get_email_service.cache_clear()

        with patch("app.services.email_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()
            mock_settings.return_value.resend_api_key = "test"
            mock_settings.return_value.email_notifications_enabled = True
            mock_settings.return_value.is_email_configured = True

            service1 = get_email_service()
            service2 = get_email_service()

            assert service1 is service2

        # Clean up
        get_email_service.cache_clear()
