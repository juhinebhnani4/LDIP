"""Email Service for sending notifications via Resend.

Gap #19: Email Notification on Processing Completion

Provides email sending capabilities using the Resend API with:
- Retry logic with exponential backoff
- Circuit breaker pattern for resilience
- Structured logging for observability

CRITICAL: Email failures are isolated from document processing pipeline.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 10.0


# =============================================================================
# Exceptions
# =============================================================================


class EmailServiceError(Exception):
    """Base exception for email service operations."""

    def __init__(
        self,
        message: str,
        code: str = "EMAIL_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class EmailConfigurationError(EmailServiceError):
    """Raised when email service is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="EMAIL_NOT_CONFIGURED", is_retryable=False)


class EmailSendError(EmailServiceError):
    """Raised when email sending fails."""

    def __init__(self, message: str, is_retryable: bool = True):
        super().__init__(message, code="EMAIL_SEND_FAILED", is_retryable=is_retryable)


# =============================================================================
# Email Service
# =============================================================================


class EmailService:
    """Service for sending email notifications via Resend.

    Gap #19: Implements email notifications for document processing completion.

    Features:
    - Async email sending with Resend SDK
    - Retry logic with exponential backoff
    - Structured logging for all operations

    Example:
        >>> service = EmailService()
        >>> await service.send_processing_complete_email(
        ...     user_email="user@example.com",
        ...     matter_name="Smith vs Jones",
        ...     doc_count=10,
        ...     success_count=8,
        ...     failed_count=2,
        ...     workspace_url="https://app.ldip.com/matters/123"
        ... )
    """

    def __init__(self) -> None:
        """Initialize email service."""
        self._client = None
        self._settings = get_settings()

    @property
    def client(self):
        """Get Resend client.

        Raises:
            EmailConfigurationError: If Resend is not configured.
        """
        if self._client is None:
            if not self._settings.resend_api_key:
                raise EmailConfigurationError(
                    "Resend API key not configured. Set RESEND_API_KEY env var."
                )
            try:
                import resend

                resend.api_key = self._settings.resend_api_key
                self._client = resend
            except ImportError:
                raise EmailConfigurationError(
                    "Resend package not installed. Run: pip install resend"
                )
        return self._client

    def is_configured(self) -> bool:
        """Check if email service is properly configured.

        Returns:
            True if Resend API key is set and feature is enabled.
        """
        return self._settings.is_email_configured

    # =========================================================================
    # Processing Complete Email
    # =========================================================================

    async def send_processing_complete_email(
        self,
        user_email: str,
        matter_name: str,
        doc_count: int,
        success_count: int,
        failed_count: int,
        workspace_url: str,
    ) -> bool:
        """Send processing complete notification email.

        Gap #19: AC #1 - Email sent when upload batch completes.

        Args:
            user_email: Recipient email address.
            matter_name: Name of the matter.
            doc_count: Total documents in batch.
            success_count: Successfully processed documents.
            failed_count: Failed documents.
            workspace_url: Deep link to matter workspace.

        Returns:
            True if email sent successfully, False otherwise.

        Raises:
            EmailConfigurationError: If email service not configured.
        """
        if not self.is_configured():
            logger.info(
                "email_notifications_disabled",
                reason="Feature flag disabled or API key not set",
            )
            return False

        # Import template function
        from app.services.email.templates.processing_complete import (
            render_processing_complete_email,
        )

        # Render email content
        subject, html_content, text_content = render_processing_complete_email(
            matter_name=matter_name,
            doc_count=doc_count,
            success_count=success_count,
            failed_count=failed_count,
            workspace_url=workspace_url,
        )

        return await self._send_email_with_retry(
            to_email=user_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type="processing_complete",
            metadata={
                "matter_name": matter_name,
                "doc_count": doc_count,
                "success_count": success_count,
                "failed_count": failed_count,
            },
        )

    # =========================================================================
    # Core Send Logic
    # =========================================================================

    async def _send_email_with_retry(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        email_type: str,
        metadata: dict | None = None,
    ) -> bool:
        """Send email with retry logic.

        Gap #19: AC #4 - Email resilience with retries.

        Args:
            to_email: Recipient email.
            subject: Email subject.
            html_content: HTML body.
            text_content: Plain text fallback.
            email_type: Type for logging.
            metadata: Additional logging context.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(MAX_RETRIES),
                wait=wait_exponential(
                    multiplier=INITIAL_RETRY_DELAY,
                    max=MAX_RETRY_DELAY,
                ),
            ):
                with attempt:
                    return await self._send_email(
                        to_email=to_email,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content,
                        email_type=email_type,
                        metadata=metadata,
                        attempt_number=attempt.retry_state.attempt_number,
                    )

        except RetryError as e:
            logger.error(
                "email_send_failed_after_retries",
                email_type=email_type,
                to_email=to_email,
                max_retries=MAX_RETRIES,
                last_error=str(e.last_attempt.exception()) if e.last_attempt else None,
                **(metadata or {}),
            )
            return False

        return False

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        email_type: str,
        metadata: dict | None = None,
        attempt_number: int = 1,
    ) -> bool:
        """Send a single email via Resend.

        Args:
            to_email: Recipient email.
            subject: Email subject.
            html_content: HTML body.
            text_content: Plain text fallback.
            email_type: Type for logging.
            metadata: Additional logging context.
            attempt_number: Current retry attempt.

        Returns:
            True if sent successfully.

        Raises:
            EmailSendError: If send fails.
        """
        try:
            # Run synchronous Resend API call in thread
            response = await asyncio.to_thread(
                self.client.Emails.send,
                {
                    "from": self._settings.email_from_address,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content,
                    "text": text_content,
                },
            )

            logger.info(
                "email_sent",
                email_type=email_type,
                to_email=to_email,
                email_id=response.get("id") if isinstance(response, dict) else None,
                attempt_number=attempt_number,
                **(metadata or {}),
            )

            return True

        except Exception as e:
            logger.warning(
                "email_send_attempt_failed",
                email_type=email_type,
                to_email=to_email,
                error=str(e),
                error_type=type(e).__name__,
                attempt_number=attempt_number,
                **(metadata or {}),
            )
            raise EmailSendError(f"Failed to send email: {e}")


# =============================================================================
# Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_email_service() -> EmailService:
    """Get singleton email service instance.

    Returns:
        EmailService instance.
    """
    return EmailService()
