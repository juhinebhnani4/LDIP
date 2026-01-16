"""Summary Verification Service for managing verification decisions and notes.

Story 14.4: Summary Verification API (Task 4)

Provides CRUD operations for summary section verifications and notes.
Uses Supabase for persistence with RLS enforcement.

CRITICAL: All operations respect matter isolation via RLS policies.
"""

import asyncio
from datetime import UTC, datetime
from functools import lru_cache

import structlog

from app.models.summary import (
    SummaryNoteRecord,
    SummarySectionTypeEnum,
    SummaryVerificationDecisionEnum,
    SummaryVerificationRecord,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 14.4: Exceptions
# =============================================================================


class SummaryVerificationServiceError(Exception):
    """Base exception for summary verification service."""

    def __init__(
        self,
        message: str,
        code: str = "VERIFICATION_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class VerificationNotFoundError(SummaryVerificationServiceError):
    """Raised when a verification record is not found."""

    def __init__(self, message: str = "Verification not found"):
        super().__init__(message, code="VERIFICATION_NOT_FOUND", status_code=404)


# =============================================================================
# Story 14.4: Summary Verification Service (Task 4.1 - 4.5)
# =============================================================================


class SummaryVerificationService:
    """Service for managing summary verification decisions and notes.

    Story 14.4: Implements AC #1-5 for verification operations.

    Features:
    - Upsert verification decisions (update if exists, insert if not)
    - Add notes to sections (multiple notes per section allowed)
    - Query verifications with optional filtering
    - Check section verification status

    Example:
        >>> service = SummaryVerificationService()
        >>> verification = await service.record_verification(
        ...     matter_id="uuid",
        ...     section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
        ...     section_id="main",
        ...     decision=SummaryVerificationDecisionEnum.VERIFIED,
        ...     notes="Reviewed and approved",
        ...     user_id="user-uuid"
        ... )
    """

    def __init__(self) -> None:
        """Initialize verification service."""
        self._supabase_client = None

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            SummaryVerificationServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise SummaryVerificationServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    # =========================================================================
    # Task 4.2: Record Verification (Upsert)
    # =========================================================================

    async def record_verification(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum,
        section_id: str,
        decision: SummaryVerificationDecisionEnum,
        user_id: str,
        notes: str | None = None,
    ) -> SummaryVerificationRecord:
        """Record or update a verification decision.

        Story 14.4: AC #1 - Upsert verification record.

        Args:
            matter_id: Matter UUID.
            section_type: Type of section being verified.
            section_id: Section identifier.
            decision: Verification decision (verified/flagged).
            user_id: User making the decision.
            notes: Optional notes.

        Returns:
            SummaryVerificationRecord with created/updated record.

        Raises:
            SummaryVerificationServiceError: If operation fails.
        """
        try:
            now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

            # Build upsert data
            data = {
                "matter_id": matter_id,
                "section_type": section_type.value,
                "section_id": section_id,
                "decision": decision.value,
                "notes": notes,
                "verified_by": user_id,
                "verified_at": now,
                "updated_at": now,
            }

            # Use upsert with on_conflict to update if exists
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_verifications")
                .upsert(
                    data,
                    on_conflict="matter_id,section_type,section_id",
                )
                .execute()
            )

            if not result.data:
                raise SummaryVerificationServiceError(
                    "Failed to record verification",
                    code="UPSERT_FAILED",
                    status_code=500,
                )

            row = result.data[0]

            logger.info(
                "verification_recorded",
                matter_id=matter_id,
                section_type=section_type.value,
                section_id=section_id,
                decision=decision.value,
                user_id=user_id,
            )

            return SummaryVerificationRecord(
                id=str(row["id"]),
                matter_id=str(row["matter_id"]),
                section_type=SummarySectionTypeEnum(row["section_type"]),
                section_id=row["section_id"],
                decision=SummaryVerificationDecisionEnum(row["decision"]),
                notes=row.get("notes"),
                verified_by=str(row["verified_by"]),
                verified_at=row["verified_at"],
            )

        except SummaryVerificationServiceError:
            raise
        except Exception as e:
            logger.error(
                "record_verification_failed",
                matter_id=matter_id,
                section_type=section_type.value,
                error=str(e),
            )
            raise SummaryVerificationServiceError(
                f"Failed to record verification: {e}",
                code="VERIFICATION_FAILED",
                status_code=500,
            ) from e

    # =========================================================================
    # Task 4.3: Add Note
    # =========================================================================

    async def add_note(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum,
        section_id: str,
        text: str,
        user_id: str,
    ) -> SummaryNoteRecord:
        """Add a note to a section.

        Story 14.4: AC #2 - Insert note record.

        Args:
            matter_id: Matter UUID.
            section_type: Type of section.
            section_id: Section identifier.
            text: Note text content.
            user_id: User creating the note.

        Returns:
            SummaryNoteRecord with created record.

        Raises:
            SummaryVerificationServiceError: If operation fails.
        """
        try:
            data = {
                "matter_id": matter_id,
                "section_type": section_type.value,
                "section_id": section_id,
                "text": text.strip(),
                "created_by": user_id,
            }

            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_notes")
                .insert(data)
                .execute()
            )

            if not result.data:
                raise SummaryVerificationServiceError(
                    "Failed to add note",
                    code="INSERT_FAILED",
                    status_code=500,
                )

            row = result.data[0]

            logger.info(
                "note_added",
                matter_id=matter_id,
                section_type=section_type.value,
                section_id=section_id,
                user_id=user_id,
            )

            return SummaryNoteRecord(
                id=str(row["id"]),
                matter_id=str(row["matter_id"]),
                section_type=SummarySectionTypeEnum(row["section_type"]),
                section_id=row["section_id"],
                text=row["text"],
                created_by=str(row["created_by"]),
                created_at=row["created_at"],
            )

        except SummaryVerificationServiceError:
            raise
        except Exception as e:
            logger.error(
                "add_note_failed",
                matter_id=matter_id,
                section_type=section_type.value,
                error=str(e),
            )
            raise SummaryVerificationServiceError(
                f"Failed to add note: {e}",
                code="NOTE_FAILED",
                status_code=500,
            ) from e

    # =========================================================================
    # Task 4.4: Get Verifications
    # =========================================================================

    async def get_verifications(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum | None = None,
    ) -> list[SummaryVerificationRecord]:
        """Get verifications for a matter.

        Story 14.4: AC #3 - Query verifications with optional filter.

        Args:
            matter_id: Matter UUID.
            section_type: Optional filter by section type.

        Returns:
            List of SummaryVerificationRecord objects.
        """
        try:
            query = (
                self.supabase.table("summary_verifications")
                .select("*")
                .eq("matter_id", matter_id)
                .order("verified_at", desc=True)
            )

            if section_type:
                query = query.eq("section_type", section_type.value)

            result = await asyncio.to_thread(lambda: query.execute())

            verifications = []
            for row in result.data or []:
                verifications.append(
                    SummaryVerificationRecord(
                        id=str(row["id"]),
                        matter_id=str(row["matter_id"]),
                        section_type=SummarySectionTypeEnum(row["section_type"]),
                        section_id=row["section_id"],
                        decision=SummaryVerificationDecisionEnum(row["decision"]),
                        notes=row.get("notes"),
                        verified_by=str(row["verified_by"]),
                        verified_at=row["verified_at"],
                    )
                )

            logger.debug(
                "verifications_queried",
                matter_id=matter_id,
                section_type=section_type.value if section_type else None,
                count=len(verifications),
            )

            return verifications

        except Exception as e:
            logger.error(
                "get_verifications_failed",
                matter_id=matter_id,
                error=str(e),
            )
            # Return empty list on error to be graceful
            return []

    # =========================================================================
    # Task 4.5: Check Section Verified
    # =========================================================================

    async def check_section_verified(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum,
        section_id: str,
    ) -> bool:
        """Check if a section has been verified.

        Story 14.4: AC #7 - Check verification status.

        Args:
            matter_id: Matter UUID.
            section_type: Type of section.
            section_id: Section identifier.

        Returns:
            True if section has 'verified' decision, False otherwise.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_verifications")
                .select("decision")
                .eq("matter_id", matter_id)
                .eq("section_type", section_type.value)
                .eq("section_id", section_id)
                .eq("decision", SummaryVerificationDecisionEnum.VERIFIED.value)
                .limit(1)
                .execute()
            )

            return len(result.data or []) > 0

        except Exception as e:
            logger.debug(
                "check_section_verified_failed",
                matter_id=matter_id,
                section_type=section_type.value,
                section_id=section_id,
                error=str(e),
            )
            return False

    async def get_notes(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum | None = None,
        section_id: str | None = None,
    ) -> list[SummaryNoteRecord]:
        """Get notes for a matter.

        Args:
            matter_id: Matter UUID.
            section_type: Optional filter by section type.
            section_id: Optional filter by section ID.

        Returns:
            List of SummaryNoteRecord objects.
        """
        try:
            query = (
                self.supabase.table("summary_notes")
                .select("*")
                .eq("matter_id", matter_id)
                .order("created_at", desc=True)
            )

            if section_type:
                query = query.eq("section_type", section_type.value)
            if section_id:
                query = query.eq("section_id", section_id)

            result = await asyncio.to_thread(lambda: query.execute())

            notes = []
            for row in result.data or []:
                notes.append(
                    SummaryNoteRecord(
                        id=str(row["id"]),
                        matter_id=str(row["matter_id"]),
                        section_type=SummarySectionTypeEnum(row["section_type"]),
                        section_id=row["section_id"],
                        text=row["text"],
                        created_by=str(row["created_by"]),
                        created_at=row["created_at"],
                    )
                )

            return notes

        except Exception as e:
            logger.error(
                "get_notes_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []


# =============================================================================
# Story 14.4: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_summary_verification_service() -> SummaryVerificationService:
    """Get singleton summary verification service instance.

    Returns:
        SummaryVerificationService instance.
    """
    return SummaryVerificationService()
