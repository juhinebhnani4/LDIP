"""Service-layer exceptions for LDIP.

These exceptions are used within services and DO NOT extend HTTPException.
Routes should catch these and convert to appropriate HTTP responses.

P3.3: Standardize service layer exceptions
"""

from typing import Any


class ServiceError(Exception):
    """Base class for all service-layer exceptions.

    Attributes:
        code: Machine-readable error code (e.g., "DOCUMENT_NOT_FOUND").
        message: Human-readable error message.
        details: Optional additional context.
        status_code: Suggested HTTP status code for API responses.
        is_retryable: Whether the operation can be retried.
    """

    code: str = "SERVICE_ERROR"
    status_code: int = 500
    is_retryable: bool = False

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        is_retryable: bool | None = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        if is_retryable is not None:
            self.is_retryable = is_retryable
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "is_retryable": self.is_retryable,
        }


class NotFoundError(ServiceError):
    """Resource not found."""

    code = "NOT_FOUND"
    status_code = 404

    def __init__(
        self,
        resource: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"{resource} with ID {resource_id} not found"
        super().__init__(message, details)
        self.resource = resource
        self.resource_id = resource_id


class DocumentNotFoundError(NotFoundError):
    """Document not found."""

    code = "DOCUMENT_NOT_FOUND"

    def __init__(self, document_id: str) -> None:
        super().__init__("Document", document_id)


class MatterNotFoundError(NotFoundError):
    """Matter not found."""

    code = "MATTER_NOT_FOUND"

    def __init__(self, matter_id: str) -> None:
        super().__init__("Matter", matter_id)


class EntityNotFoundError(NotFoundError):
    """Entity not found."""

    code = "ENTITY_NOT_FOUND"

    def __init__(self, entity_id: str) -> None:
        super().__init__("Entity", entity_id)


class JobNotFoundError(NotFoundError):
    """Job not found."""

    code = "JOB_NOT_FOUND"

    def __init__(self, job_id: str) -> None:
        super().__init__("Job", job_id)


class ValidationError(ServiceError):
    """Validation failed."""

    code = "VALIDATION_ERROR"
    status_code = 400

    def __init__(
        self,
        message: str = "Validation failed",
        field_errors: list[dict[str, str]] | None = None,
    ) -> None:
        details = {"fields": field_errors} if field_errors else {}
        super().__init__(message, details)
        self.field_errors = field_errors or []


class AuthorizationError(ServiceError):
    """User not authorized for this action."""

    code = "FORBIDDEN"
    status_code = 403

    def __init__(self, action: str) -> None:
        message = f"You don't have permission to {action}"
        super().__init__(message)
        self.action = action


class ConflictError(ServiceError):
    """Resource conflict (e.g., duplicate, version mismatch)."""

    code = "CONFLICT"
    status_code = 409

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class ExternalServiceError(ServiceError):
    """External service (LLM, OCR, etc.) failed."""

    code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502
    is_retryable = True  # External failures are often transient

    def __init__(
        self,
        service_name: str,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        is_retryable: bool = True,
    ) -> None:
        full_message = f"{service_name} error: {message}"
        super().__init__(full_message, details, is_retryable=is_retryable)
        self.service_name = service_name


class DatabaseError(ServiceError):
    """Database operation failed."""

    code = "DATABASE_ERROR"
    status_code = 503
    is_retryable = True

    def __init__(
        self,
        message: str = "Database operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class RateLimitError(ServiceError):
    """Rate limit exceeded."""

    code = "RATE_LIMIT_EXCEEDED"
    status_code = 429
    is_retryable = True

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        details = {"retryAfter": retry_after} if retry_after else {}
        super().__init__(message, details, is_retryable=True)
        self.retry_after = retry_after


class PartialSuccessError(ServiceError):
    """Batch operation partially succeeded."""

    code = "PARTIAL_SUCCESS"
    status_code = 207  # Multi-Status

    def __init__(
        self,
        message: str,
        succeeded: list[str],
        failed: list[dict[str, Any]],
    ) -> None:
        details = {
            "succeeded": succeeded,
            "failed": failed,
            "successCount": len(succeeded),
            "failedCount": len(failed),
        }
        super().__init__(message, details)
        self.succeeded = succeeded
        self.failed = failed
