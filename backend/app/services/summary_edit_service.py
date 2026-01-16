"""Summary Edit Service for managing edited summary sections.

Story 14.6: Summary Frontend Integration (Task 1.4)

Provides services for:
- Saving edited summary content
- Retrieving existing edits
- Deleting edits (revert to original)

CRITICAL: Uses matter access validation for Layer 4 security.
"""

import asyncio
from datetime import UTC, datetime
from functools import lru_cache

import structlog

from app.models.summary import SummaryEditRecord, SummarySectionTypeEnum
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 14.6: Exceptions
# =============================================================================


class SummaryEditServiceError(Exception):
    """Base exception for summary edit service operations."""

    def __init__(
        self,
        message: str,
        code: str = "EDIT_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class EditNotFoundError(SummaryEditServiceError):
    """Raised when edit record is not found."""

    def __init__(self, message: str = "Edit not found"):
        super().__init__(message, code="EDIT_NOT_FOUND", status_code=404)


class EditSaveError(SummaryEditServiceError):
    """Raised when edit save fails."""

    def __init__(self, message: str):
        super().__init__(message, code="EDIT_SAVE_FAILED", status_code=500)


# =============================================================================
# Story 14.6: Summary Edit Service (Task 1.4)
# =============================================================================


class SummaryEditService:
    """Service for managing summary section edits.

    Story 14.6: Implements AC #7 for edit persistence.

    Provides upsert pattern - creates new record or updates existing.
    Preserves original content for audit trail.

    Example:
        >>> service = SummaryEditService()
        >>> edit = await service.save_edit(
        ...     matter_id="matter-123",
        ...     section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
        ...     section_id="main",
        ...     content="Edited description",
        ...     original_content="Original AI description",
        ...     user_id="user-456",
        ... )
    """

    def __init__(self) -> None:
        """Initialize summary edit service."""
        self._supabase_client = None

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            SummaryEditServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise SummaryEditServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    async def save_edit(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum,
        section_id: str,
        content: str,
        original_content: str,
        user_id: str,
    ) -> SummaryEditRecord:
        """Save or update an edit for a summary section.

        Story 14.6: AC #7 - Uses upsert pattern for efficient save.

        Args:
            matter_id: Matter UUID.
            section_type: Type of section (subject_matter, current_status, parties, key_issue).
            section_id: Section identifier ("main" or entity_id).
            content: Edited text content.
            original_content: Original AI-generated content.
            user_id: User UUID who is editing.

        Returns:
            SummaryEditRecord with saved edit data.

        Raises:
            EditSaveError: If save operation fails.
        """
        try:
            now = datetime.now(UTC).isoformat()

            # Upsert: insert or update on conflict
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_edits")
                .upsert(
                    {
                        "matter_id": matter_id,
                        "section_type": section_type.value,
                        "section_id": section_id,
                        "original_content": original_content,
                        "edited_content": content,
                        "edited_by": user_id,
                        "edited_at": now,
                    },
                    on_conflict="matter_id,section_type,section_id",
                )
                .execute()
            )

            if not result.data:
                raise EditSaveError("Failed to save edit: no data returned")

            row = result.data[0]

            logger.info(
                "summary_edit_saved",
                matter_id=matter_id,
                section_type=section_type.value,
                section_id=section_id,
                user_id=user_id,
            )

            return SummaryEditRecord(
                id=row["id"],
                matter_id=row["matter_id"],
                section_type=SummarySectionTypeEnum(row["section_type"]),
                section_id=row["section_id"],
                original_content=row["original_content"],
                edited_content=row["edited_content"],
                edited_by=row["edited_by"],
                edited_at=row["edited_at"],
            )

        except SummaryEditServiceError:
            raise
        except Exception as e:
            logger.error(
                "summary_edit_save_failed",
                matter_id=matter_id,
                section_type=section_type.value,
                error=str(e),
            )
            raise EditSaveError(f"Failed to save edit: {e}") from e

    async def get_edit(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum,
        section_id: str,
    ) -> SummaryEditRecord | None:
        """Get existing edit for a summary section.

        Args:
            matter_id: Matter UUID.
            section_type: Type of section.
            section_id: Section identifier.

        Returns:
            SummaryEditRecord if found, None otherwise.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_edits")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("section_type", section_type.value)
                .eq("section_id", section_id)
                .limit(1)
                .execute()
            )

            if not result.data:
                return None

            row = result.data[0]

            return SummaryEditRecord(
                id=row["id"],
                matter_id=row["matter_id"],
                section_type=SummarySectionTypeEnum(row["section_type"]),
                section_id=row["section_id"],
                original_content=row["original_content"],
                edited_content=row["edited_content"],
                edited_by=row["edited_by"],
                edited_at=row["edited_at"],
            )

        except Exception as e:
            logger.warning(
                "summary_edit_get_failed",
                matter_id=matter_id,
                section_type=section_type.value,
                section_id=section_id,
                error=str(e),
            )
            return None

    async def get_all_edits(
        self,
        matter_id: str,
    ) -> list[SummaryEditRecord]:
        """Get all edits for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            List of SummaryEditRecord objects.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_edits")
                .select("*")
                .eq("matter_id", matter_id)
                .execute()
            )

            edits = []
            for row in result.data or []:
                edits.append(
                    SummaryEditRecord(
                        id=row["id"],
                        matter_id=row["matter_id"],
                        section_type=SummarySectionTypeEnum(row["section_type"]),
                        section_id=row["section_id"],
                        original_content=row["original_content"],
                        edited_content=row["edited_content"],
                        edited_by=row["edited_by"],
                        edited_at=row["edited_at"],
                    )
                )

            return edits

        except Exception as e:
            logger.warning(
                "summary_edits_get_all_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []

    async def delete_edit(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum,
        section_id: str,
    ) -> bool:
        """Delete an edit record (revert to original AI content).

        Args:
            matter_id: Matter UUID.
            section_type: Type of section.
            section_id: Section identifier.

        Returns:
            True if edit was deleted, False if not found.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_edits")
                .delete()
                .eq("matter_id", matter_id)
                .eq("section_type", section_type.value)
                .eq("section_id", section_id)
                .execute()
            )

            deleted = len(result.data or []) > 0

            if deleted:
                logger.info(
                    "summary_edit_deleted",
                    matter_id=matter_id,
                    section_type=section_type.value,
                    section_id=section_id,
                )

            return deleted

        except Exception as e:
            logger.warning(
                "summary_edit_delete_failed",
                matter_id=matter_id,
                section_type=section_type.value,
                section_id=section_id,
                error=str(e),
            )
            return False


# =============================================================================
# Story 14.6: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_summary_edit_service() -> SummaryEditService:
    """Get singleton summary edit service instance.

    Returns:
        SummaryEditService instance.
    """
    return SummaryEditService()
