"""Verification service module for attorney finding verification.

Story 8-4: Implement Finding Verifications Table
Epic 8: Safety Layer (Guardrails, Policing, Verification)

This module provides:
- VerificationService: Main service for managing finding verifications
- ExportEligibilityService: Checks if matter is eligible for export

Exports:
    - VerificationService: Main verification service class
    - get_verification_service: Factory for singleton service instance
    - reset_verification_service: Reset singleton for testing
    - ExportEligibilityService: Export eligibility checker
    - get_export_eligibility_service: Factory for export service
"""

from app.services.verification.verification_service import (
    VerificationService,
    VerificationServiceError,
    get_verification_service,
    reset_verification_service,
)
from app.services.verification.export_eligibility import (
    ExportEligibilityService,
    get_export_eligibility_service,
)

__all__ = [
    # Verification Service
    "VerificationService",
    "VerificationServiceError",
    "get_verification_service",
    "reset_verification_service",
    # Export Eligibility
    "ExportEligibilityService",
    "get_export_eligibility_service",
]
