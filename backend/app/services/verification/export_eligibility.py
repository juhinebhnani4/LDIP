"""Export eligibility service for finding verification checks.

Story 8-4: Task 8 - Export Eligibility Check
Epic 8: Safety Layer (Guardrails, Policing, Verification)

Story 3.2: Export Gate Check based on matter verification mode
Epic 3: Compliance & UX

This service checks if a matter is eligible for export based on:
- Matter verification_mode: 'advisory' or 'required'
- In 'advisory' mode (default):
  - Unverified findings with confidence < 70% block export
  - Unverified findings with confidence 70-90% show warning
  - All findings verified or > 90% confidence allow export
- In 'required' mode (court-ready):
  - ALL pending findings block export (100% verification required)
  - No warnings, only blocking findings

Implements:
- AC #5: Findings < 70% confidence require verification before export
- ADR-004: Verification Tier Thresholds
- Story 3.2: Configurable verification gates per matter
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.models.verification import (
    ExportBlockingFinding,
    ExportEligibilityResult,
    ExportWarningFinding,
    VerificationDecision,
)

if TYPE_CHECKING:
    from supabase import Client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 8-4: ExportEligibilityService (Task 8.1-8.4)
# =============================================================================


class ExportEligibilityService:
    """Service for checking export eligibility based on verification status.

    Story 8-4: AC #5 - Export blocked for unverified low-confidence findings.

    Logic:
    - Findings with confidence < 70% and decision='pending' block export
    - All other combinations allow export (may show warnings)

    Example:
        >>> service = get_export_eligibility_service()
        >>> result = await service.check_export_eligibility(
        ...     matter_id="uuid",
        ...     supabase=supabase_client,
        ... )
        >>> if not result.eligible:
        ...     print(f"Export blocked: {result.blocking_count} findings need verification")
    """

    def __init__(self) -> None:
        """Initialize export eligibility service.

        Story 8-4: Task 8.1 - Service initialization.
        Story 12-3: Added warning threshold for 70-90% confidence findings.
        """
        settings = get_settings()
        self._export_block_threshold = settings.verification_export_block_below
        self._warning_upper_threshold = settings.verification_threshold_optional

        logger.info(
            "export_eligibility_service_initialized",
            export_block_threshold=self._export_block_threshold,
            warning_upper_threshold=self._warning_upper_threshold,
        )

    async def check_export_eligibility(
        self,
        matter_id: str,
        supabase: Client,
    ) -> ExportEligibilityResult:
        """Check if matter is eligible for export.

        Story 8-4: AC #5, Task 8.2 - Returns True/False + list of blocking findings.
        Story 12-3: AC #2 - Also returns warning findings (70-90% confidence).
        Story 3.2: Considers matter verification_mode for court-ready mode.

        Args:
            matter_id: Matter UUID to check.
            supabase: Supabase client.

        Returns:
            ExportEligibilityResult with eligibility, blocking, and warning findings.
        """
        start_time = time.perf_counter()

        try:
            # Story 3.2: First, fetch matter's verification_mode
            matter_result = supabase.table("matters").select(
                "verification_mode"
            ).eq("id", matter_id).execute()

            verification_mode = "advisory"  # Default
            if matter_result.data and len(matter_result.data) > 0:
                verification_mode = matter_result.data[0].get("verification_mode", "advisory")

            is_court_ready = verification_mode == "required"

            if is_court_ready:
                # Story 3.2: Court-ready mode - ALL pending findings block export
                blocking_result = supabase.table("finding_verifications").select(
                    "id, finding_id, finding_type, finding_summary, confidence_before"
                ).eq("matter_id", matter_id).eq(
                    "decision", VerificationDecision.PENDING.value
                ).execute()

                blocking_findings = [
                    ExportBlockingFinding(
                        verification_id=r["id"],
                        finding_id=r.get("finding_id"),
                        finding_type=r["finding_type"],
                        finding_summary=r["finding_summary"],
                        confidence=r["confidence_before"],
                    )
                    for r in blocking_result.data
                ]

                # In court-ready mode, no warnings - everything blocks
                warning_findings: list[ExportWarningFinding] = []

                blocking_count = len(blocking_findings)
                warning_count = 0
                eligible = blocking_count == 0

                # Generate message for court-ready mode
                if eligible:
                    message = "Court-ready: All findings verified. Export is allowed."
                else:
                    message = (
                        f"Court-ready mode: {blocking_count} finding(s) require verification "
                        f"before export. 100% verification is required."
                    )
            else:
                # Story 8-4: Advisory mode - use confidence thresholds
                # LATENCY FIX: Parallelize both queries with asyncio.gather
                blocking_result, warning_result = await asyncio.gather(
                    # Query for pending verifications at or below blocking threshold
                    asyncio.to_thread(
                        lambda: supabase.table("finding_verifications").select(
                            "id, finding_id, finding_type, finding_summary, confidence_before"
                        ).eq("matter_id", matter_id).eq(
                            "decision", VerificationDecision.PENDING.value
                        ).lte(
                            "confidence_before", self._export_block_threshold
                        ).execute()
                    ),
                    # Story 12-3: Query for warning findings (70-90% confidence, pending)
                    asyncio.to_thread(
                        lambda: supabase.table("finding_verifications").select(
                            "id, finding_id, finding_type, finding_summary, confidence_before"
                        ).eq("matter_id", matter_id).eq(
                            "decision", VerificationDecision.PENDING.value
                        ).gt(
                            "confidence_before", self._export_block_threshold
                        ).lte(
                            "confidence_before", self._warning_upper_threshold
                        ).execute()
                    ),
                )

                blocking_findings = [
                    ExportBlockingFinding(
                        verification_id=r["id"],
                        finding_id=r.get("finding_id"),
                        finding_type=r["finding_type"],
                        finding_summary=r["finding_summary"],
                        confidence=r["confidence_before"],
                    )
                    for r in blocking_result.data
                ]

                warning_findings = [
                    ExportWarningFinding(
                        verification_id=r["id"],
                        finding_id=r.get("finding_id"),
                        finding_type=r["finding_type"],
                        finding_summary=r["finding_summary"],
                        confidence=r["confidence_before"],
                    )
                    for r in warning_result.data
                ]

                blocking_count = len(blocking_findings)
                warning_count = len(warning_findings)
                eligible = blocking_count == 0

                # Generate message for advisory mode
                if eligible:
                    if warning_count > 0:
                        message = (
                            f"Export allowed with {warning_count} warning(s). "
                            f"Some findings (70-90% confidence) are suggested for verification."
                        )
                    else:
                        message = "All required verifications complete. Export is allowed."
                else:
                    message = (
                        f"Export blocked: {blocking_count} finding(s) with confidence "
                        f"< {self._export_block_threshold}% require verification before export."
                    )

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "export_eligibility_checked",
                matter_id=matter_id,
                verification_mode=verification_mode,
                eligible=eligible,
                blocking_count=blocking_count,
                warning_count=warning_count,
                elapsed_ms=round(elapsed_ms, 2),
            )

            return ExportEligibilityResult(
                eligible=eligible,
                verification_mode=verification_mode,
                blocking_findings=blocking_findings,
                blocking_count=blocking_count,
                warning_findings=warning_findings,
                warning_count=warning_count,
                message=message,
            )

        except Exception as e:
            logger.error(
                "export_eligibility_check_failed",
                matter_id=matter_id,
                error=str(e),
            )
            # On error, default to blocked (fail-safe)
            # Code Review Fix: Include verification_mode to match TypeScript interface
            return ExportEligibilityResult(
                eligible=False,
                verification_mode="advisory",  # Default to advisory on error
                blocking_findings=[],
                blocking_count=0,
                warning_findings=[],
                warning_count=0,
                message=f"Export eligibility check failed: {e}. Export blocked for safety.",
            )

    async def get_blocking_findings(
        self,
        matter_id: str,
        supabase: Client,
    ) -> list[ExportBlockingFinding]:
        """Get list of findings blocking export.

        Story 8-4: Task 8.3 - Findings < 70% without verification.

        Args:
            matter_id: Matter UUID.
            supabase: Supabase client.

        Returns:
            List of ExportBlockingFinding records.
        """
        result = await self.check_export_eligibility(matter_id, supabase)
        return result.blocking_findings


# =============================================================================
# Story 8-4: Singleton Factory
# =============================================================================

# Singleton instance (thread-safe)
_export_eligibility_service: ExportEligibilityService | None = None
_service_lock = threading.Lock()


def get_export_eligibility_service() -> ExportEligibilityService:
    """Get singleton ExportEligibilityService instance.

    Story 8-4: Thread-safe singleton factory.

    Returns:
        ExportEligibilityService singleton instance.
    """
    global _export_eligibility_service  # noqa: PLW0603

    if _export_eligibility_service is None:
        with _service_lock:
            # Double-check locking pattern
            if _export_eligibility_service is None:
                _export_eligibility_service = ExportEligibilityService()

    return _export_eligibility_service


def reset_export_eligibility_service() -> None:
    """Reset singleton for testing.

    Story 8-4: Reset function for test isolation.
    """
    global _export_eligibility_service  # noqa: PLW0603

    with _service_lock:
        _export_eligibility_service = None

    logger.debug("export_eligibility_service_reset")
