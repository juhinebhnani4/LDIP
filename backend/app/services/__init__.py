"""Services module - business logic layer."""

from app.services.matter_service import (
    CannotRemoveOwnerError,
    InsufficientPermissionsError,
    MatterNotFoundError,
    MatterService,
    MatterServiceError,
    MemberAlreadyExistsError,
    UserNotFoundError,
)
from app.services.verification import (
    ExportEligibilityService,
    VerificationService,
    VerificationServiceError,
    VerificationNotFoundError,
    get_export_eligibility_service,
    get_verification_service,
    reset_verification_service,
    reset_export_eligibility_service,
)

__all__ = [
    # Matter service
    "MatterService",
    "MatterServiceError",
    "MatterNotFoundError",
    "InsufficientPermissionsError",
    "MemberAlreadyExistsError",
    "CannotRemoveOwnerError",
    "UserNotFoundError",
    # Verification service (Story 8-4)
    "ExportEligibilityService",
    "VerificationService",
    "VerificationServiceError",
    "VerificationNotFoundError",
    "get_export_eligibility_service",
    "get_verification_service",
    "reset_verification_service",
    "reset_export_eligibility_service",
]
