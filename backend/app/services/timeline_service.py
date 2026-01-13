"""Timeline service for database operations.

Handles saving and retrieving extracted dates/events
for the Timeline Construction Engine.

Story 4-1: Date Extraction with Gemini
"""

import asyncio
from functools import lru_cache
from math import ceil

import structlog

from app.models.timeline import (
    ExtractedDate,
    PaginationMeta,
    RawDateListItem,
    RawDatesListResponse,
    RawEvent,
)
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class TimelineServiceError(Exception):
    """Base exception for timeline service operations."""

    def __init__(self, message: str, code: str = "TIMELINE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EventNotFoundError(TimelineServiceError):
    """Raised when event is not found."""

    def __init__(self, message: str):
        super().__init__(message, code="EVENT_NOT_FOUND")


# =============================================================================
# Service Implementation
# =============================================================================


class TimelineService:
    """Service for timeline database operations.

    Handles CRUD operations for the events table, specifically for
    raw date events extracted from documents.

    Uses the service client to bypass RLS since the backend
    has already validated access via the document's matter.
    """

    def __init__(self) -> None:
        """Initialize timeline service."""
        self._client = None

    @property
    def client(self):
        """Get Supabase service client.

        Raises:
            TimelineServiceError: If Supabase is not configured.
        """
        if self._client is None:
            self._client = get_service_client()
            if self._client is None:
                raise TimelineServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                )
        return self._client

    async def save_extracted_dates(
        self,
        matter_id: str,
        document_id: str,
        dates: list[ExtractedDate],
    ) -> list[str]:
        """Save extracted dates to events table.

        Creates raw_date events from extracted dates.
        These will be classified in Story 4-2.

        Args:
            matter_id: Matter UUID for isolation.
            document_id: Source document UUID.
            dates: List of ExtractedDate objects.

        Returns:
            List of created event UUIDs.

        Raises:
            TimelineServiceError: If save fails.
        """
        if not dates:
            logger.debug(
                "timeline_save_empty",
                matter_id=matter_id,
                document_id=document_id,
            )
            return []

        # Convert dates to event records
        event_records = []
        for date_obj in dates:
            # Combine context into description
            context_parts = []
            if date_obj.context_before:
                context_parts.append(date_obj.context_before)
            context_parts.append(f"[{date_obj.date_text}]")
            if date_obj.context_after:
                context_parts.append(date_obj.context_after)

            description = " ".join(context_parts)

            # Add ambiguity marker to description if date is ambiguous
            # Format: [AMBIGUOUS: reason] at the start of description
            if date_obj.is_ambiguous and date_obj.ambiguity_reason:
                description = f"[AMBIGUOUS: {date_obj.ambiguity_reason}] {description}"
            elif date_obj.is_ambiguous:
                description = f"[AMBIGUOUS] {description}"

            event_records.append({
                "matter_id": matter_id,
                "document_id": document_id,
                "event_date": date_obj.extracted_date.isoformat(),
                "event_date_precision": date_obj.date_precision,
                "event_date_text": date_obj.date_text,
                "event_type": "raw_date",  # Pre-classification type
                "description": description[:5000],  # Limit description length
                "source_page": date_obj.page_number,
                "source_bbox_ids": date_obj.bbox_ids,
                "confidence": date_obj.confidence,
                "is_manual": False,
            })

        def _insert():
            return (
                self.client.table("events")
                .insert(event_records)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                event_ids = [row["id"] for row in response.data]
                logger.info(
                    "timeline_dates_saved",
                    matter_id=matter_id,
                    document_id=document_id,
                    event_count=len(event_ids),
                )
                return event_ids

            raise TimelineServiceError("Failed to save dates - no data returned")

        except TimelineServiceError:
            raise
        except Exception as e:
            logger.error(
                "timeline_save_failed",
                error=str(e),
                matter_id=matter_id,
                document_id=document_id,
            )
            raise TimelineServiceError(f"Failed to save extracted dates: {e}")

    def save_extracted_dates_sync(
        self,
        matter_id: str,
        document_id: str,
        dates: list[ExtractedDate],
    ) -> list[str]:
        """Synchronous version of save_extracted_dates.

        For use in Celery tasks.

        Args:
            matter_id: Matter UUID.
            document_id: Document UUID.
            dates: List of ExtractedDate objects.

        Returns:
            List of created event UUIDs.
        """
        if not dates:
            return []

        event_records = []
        for date_obj in dates:
            context_parts = []
            if date_obj.context_before:
                context_parts.append(date_obj.context_before)
            context_parts.append(f"[{date_obj.date_text}]")
            if date_obj.context_after:
                context_parts.append(date_obj.context_after)

            description = " ".join(context_parts)

            # Add ambiguity marker to description if date is ambiguous
            if date_obj.is_ambiguous and date_obj.ambiguity_reason:
                description = f"[AMBIGUOUS: {date_obj.ambiguity_reason}] {description}"
            elif date_obj.is_ambiguous:
                description = f"[AMBIGUOUS] {description}"

            event_records.append({
                "matter_id": matter_id,
                "document_id": document_id,
                "event_date": date_obj.extracted_date.isoformat(),
                "event_date_precision": date_obj.date_precision,
                "event_date_text": date_obj.date_text,
                "event_type": "raw_date",
                "description": description[:5000],
                "source_page": date_obj.page_number,
                "source_bbox_ids": date_obj.bbox_ids,
                "confidence": date_obj.confidence,
                "is_manual": False,
            })

        try:
            response = (
                self.client.table("events")
                .insert(event_records)
                .execute()
            )

            if response.data:
                event_ids = [row["id"] for row in response.data]
                logger.info(
                    "timeline_dates_saved_sync",
                    matter_id=matter_id,
                    document_id=document_id,
                    event_count=len(event_ids),
                )
                return event_ids

            return []

        except Exception as e:
            logger.error(
                "timeline_save_sync_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise TimelineServiceError(f"Failed to save extracted dates: {e}")

    async def get_raw_dates_for_document(
        self,
        document_id: str,
        matter_id: str,
    ) -> list[RawEvent]:
        """Get all raw dates extracted from a document.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for validation.

        Returns:
            List of RawEvent records ordered by event_date.
        """
        def _query():
            return (
                self.client.table("events")
                .select("*")
                .eq("document_id", document_id)
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
                .order("event_date", desc=False)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if response.data:
            return [self._db_row_to_raw_event(row) for row in response.data]
        return []

    async def get_timeline_for_matter(
        self,
        matter_id: str,
        event_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> RawDatesListResponse:
        """Get all events for a matter (timeline view).

        Args:
            matter_id: Matter UUID.
            event_type: Optional filter by event type.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            RawDatesListResponse with paginated events.
        """
        def _query():
            query = (
                self.client.table("events")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
            )

            if event_type:
                query = query.eq("event_type", event_type)

            # Order by event_date
            query = query.order("event_date", desc=False)

            # Pagination
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            return query.execute()

        response = await asyncio.to_thread(_query)

        items = [
            self._db_row_to_list_item(row)
            for row in (response.data or [])
        ]

        total = response.count or 0
        total_pages = ceil(total / per_page) if per_page > 0 else 0

        return RawDatesListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    async def get_raw_dates_for_matter(
        self,
        matter_id: str,
        document_id: str | None = None,
        page_filter: int | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> RawDatesListResponse:
        """Get raw dates for a matter with optional filters.

        Args:
            matter_id: Matter UUID.
            document_id: Optional document filter.
            page_filter: Optional page number filter.
            page: Page number for pagination.
            per_page: Items per page.

        Returns:
            RawDatesListResponse with paginated raw dates.
        """
        def _query():
            query = (
                self.client.table("events")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
            )

            if document_id:
                query = query.eq("document_id", document_id)

            if page_filter is not None:
                query = query.eq("source_page", page_filter)

            # Order by event_date
            query = query.order("event_date", desc=False)

            # Pagination
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            return query.execute()

        response = await asyncio.to_thread(_query)

        items = [
            self._db_row_to_list_item(row)
            for row in (response.data or [])
        ]

        total = response.count or 0
        total_pages = ceil(total / per_page) if per_page > 0 else 0

        return RawDatesListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    async def get_event_by_id(
        self,
        event_id: str,
        matter_id: str,
    ) -> RawEvent | None:
        """Get a single event by ID.

        Args:
            event_id: Event UUID.
            matter_id: Matter UUID for validation.

        Returns:
            RawEvent if found, None otherwise.
        """
        def _query():
            return (
                self.client.table("events")
                .select("*")
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if response.data:
            return self._db_row_to_raw_event(response.data[0])
        return None

    async def delete_raw_dates_for_document(
        self,
        document_id: str,
        matter_id: str,
    ) -> int:
        """Delete all raw dates for a document (for reprocessing).

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for validation.

        Returns:
            Number of deleted events.
        """
        def _delete():
            return (
                self.client.table("events")
                .delete()
                .eq("document_id", document_id)
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
                .execute()
            )

        try:
            response = await asyncio.to_thread(_delete)

            deleted_count = len(response.data) if response.data else 0
            logger.info(
                "timeline_dates_deleted",
                document_id=document_id,
                matter_id=matter_id,
                deleted_count=deleted_count,
            )
            return deleted_count

        except Exception as e:
            logger.error(
                "timeline_delete_failed",
                error=str(e),
                document_id=document_id,
            )
            raise TimelineServiceError(f"Failed to delete raw dates: {e}")

    async def has_dates_for_document(
        self,
        document_id: str,
        matter_id: str,
    ) -> bool:
        """Check if a document already has extracted dates.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID.

        Returns:
            True if document has existing raw_date events.
        """
        def _query():
            return (
                self.client.table("events")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_query)
        return (response.count or 0) > 0

    def has_dates_for_document_sync(
        self,
        document_id: str,
        matter_id: str,
    ) -> bool:
        """Synchronous check for existing dates.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID.

        Returns:
            True if document has existing raw_date events.
        """
        try:
            response = (
                self.client.table("events")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
                .limit(1)
                .execute()
            )
            return (response.count or 0) > 0
        except Exception:
            return False

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_ambiguity_from_description(
        self, description: str
    ) -> tuple[bool, str | None, str]:
        """Extract ambiguity info from description prefix.

        Parses descriptions with format: [AMBIGUOUS: reason] or [AMBIGUOUS]

        Args:
            description: Event description that may contain ambiguity marker.

        Returns:
            Tuple of (is_ambiguous, ambiguity_reason, clean_description).
        """
        import re

        if not description:
            return False, None, ""

        # Match [AMBIGUOUS: reason] or [AMBIGUOUS] at start
        match = re.match(r"^\[AMBIGUOUS(?::\s*([^\]]+))?\]\s*", description)
        if match:
            is_ambiguous = True
            ambiguity_reason = match.group(1)  # None if no reason
            clean_description = description[match.end():]
            return is_ambiguous, ambiguity_reason, clean_description

        return False, None, description

    def _db_row_to_raw_event(self, row: dict) -> RawEvent:
        """Convert database row to RawEvent model."""
        from datetime import datetime, date

        event_date = row.get("event_date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)

        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        # Extract ambiguity info from description
        description = row.get("description", "")
        is_ambiguous, ambiguity_reason, clean_description = (
            self._parse_ambiguity_from_description(description)
        )

        return RawEvent(
            id=row["id"],
            matter_id=row["matter_id"],
            document_id=row.get("document_id"),
            event_date=event_date,
            event_date_precision=row.get("event_date_precision", "day"),
            event_date_text=row.get("event_date_text"),
            event_type=row["event_type"],
            description=clean_description,
            entities_involved=row.get("entities_involved") or [],
            source_page=row.get("source_page"),
            source_bbox_ids=row.get("source_bbox_ids") or [],
            confidence=row.get("confidence", 0.8),
            is_manual=row.get("is_manual", False),
            created_by=row.get("created_by"),
            created_at=created_at,
            updated_at=updated_at,
            is_ambiguous=is_ambiguous,
            ambiguity_reason=ambiguity_reason,
        )

    def _db_row_to_list_item(self, row: dict) -> RawDateListItem:
        """Convert database row to list item."""
        from datetime import date

        event_date = row.get("event_date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)

        # Extract ambiguity info from description
        description = row.get("description", "")
        is_ambiguous, _, clean_description = (
            self._parse_ambiguity_from_description(description)
        )

        return RawDateListItem(
            id=row["id"],
            event_date=event_date,
            event_date_precision=row.get("event_date_precision", "day"),
            event_date_text=row.get("event_date_text"),
            description=clean_description,
            document_id=row.get("document_id"),
            source_page=row.get("source_page"),
            confidence=row.get("confidence", 0.8),
            is_ambiguous=is_ambiguous,
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_timeline_service() -> TimelineService:
    """Get singleton timeline service instance.

    Returns:
        TimelineService instance.
    """
    return TimelineService()
