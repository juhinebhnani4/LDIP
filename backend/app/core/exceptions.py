"""Custom exception classes for the application."""

from typing import Any

from fastapi import HTTPException


class AppException(HTTPException):
    """Base application exception with structured error response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.error_details = details or {}
        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "details": self.error_details,
                }
            },
        )


class NotFoundError(AppException):
    """Resource not found exception."""

    def __init__(
        self,
        resource: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource} with ID {resource_id} not found",
            status_code=404,
            details=details,
        )


class MatterNotFoundError(NotFoundError):
    """Matter not found exception."""

    def __init__(self, matter_id: str) -> None:
        super().__init__(resource="Matter", resource_id=matter_id)


class DocumentNotFoundError(NotFoundError):
    """Document not found exception."""

    def __init__(self, document_id: str) -> None:
        super().__init__(resource="Document", resource_id=document_id)


class InsufficientPermissionsError(AppException):
    """Insufficient permissions exception."""

    def __init__(self, action: str) -> None:
        super().__init__(
            code="INSUFFICIENT_PERMISSIONS",
            message=f"You don't have permission to {action}",
            status_code=403,
        )


class ValidationError(AppException):
    """Validation error exception."""

    def __init__(
        self,
        message: str = "Invalid request data",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details=details,
        )


class InternalError(AppException):
    """Internal server error exception."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        correlation_id: str | None = None,
    ) -> None:
        details = {}
        if correlation_id:
            details["correlation_id"] = correlation_id
        super().__init__(
            code="INTERNAL_ERROR",
            message=message,
            status_code=500,
            details=details,
        )
