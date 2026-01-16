"""Timeline service for database operations.

Handles saving and retrieving extracted dates/events
for the Timeline Construction Engine.

Story 4-1: Date Extraction with Gemini
Story 4-2: Event Classification
"""

import asyncio
from functools import lru_cache
from math import ceil

import structlog

from app.models.timeline import (
    ClassifiedEvent,
    ClassifiedEventsListResponse,
    EntityReference,
    EventClassificationListItem,
    EventClassificationResult,
    EventType,
    ExtractedDate,
    ManualEventCreateRequest,
    ManualEventResponse,
    ManualEventUpdateRequest,
    PaginationMeta,
    RawDateListItem,
    RawDatesListResponse,
    RawEvent,
    UnclassifiedEventItem,
    UnclassifiedEventsResponse,
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
    # Event Classification Methods (Story 4-2)
    # =========================================================================

    async def update_event_classification(
        self,
        event_id: str,
        matter_id: str,
        event_type: str,
        confidence: float,
        is_manual: bool = False,
    ) -> bool:
        """Update an event's classification.

        Args:
            event_id: Event UUID to update.
            matter_id: Matter UUID for validation.
            event_type: New event type (filing, notice, etc.).
            confidence: Classification confidence (0-1).
            is_manual: If True, this is a manual human classification.

        Returns:
            True if update succeeded.

        Raises:
            TimelineServiceError: If update fails.
        """
        # For auto-classification (is_manual=False), set verified=False
        # as it needs human review if confidence is low.
        # For manual classification, verified=True as human has confirmed.

        def _update():
            return (
                self.client.table("events")
                .update({
                    "event_type": event_type,
                    "confidence": confidence,
                    "is_manual": is_manual,
                })
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_update)

            if response.data:
                logger.info(
                    "event_classification_updated",
                    event_id=event_id,
                    matter_id=matter_id,
                    event_type=event_type,
                    confidence=confidence,
                )
                return True

            logger.warning(
                "event_classification_no_match",
                event_id=event_id,
                matter_id=matter_id,
            )
            return False

        except Exception as e:
            logger.error(
                "event_classification_update_failed",
                error=str(e),
                event_id=event_id,
            )
            raise TimelineServiceError(f"Failed to update event classification: {e}")

    def update_event_classification_sync(
        self,
        event_id: str,
        matter_id: str,
        event_type: str,
        confidence: float,
        is_manual: bool = False,
    ) -> bool:
        """Synchronous version of update_event_classification.

        For use in Celery tasks.

        Args:
            event_id: Event UUID to update.
            matter_id: Matter UUID.
            event_type: New event type.
            confidence: Classification confidence.
            is_manual: If True, this is a manual human classification.

        Returns:
            True if update succeeded.
        """
        try:
            response = (
                self.client.table("events")
                .update({
                    "event_type": event_type,
                    "confidence": confidence,
                    "is_manual": is_manual,
                })
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .execute()
            )

            if response.data:
                logger.info(
                    "event_classification_updated_sync",
                    event_id=event_id,
                    event_type=event_type,
                    is_manual=is_manual,
                )
                return True
            return False

        except Exception as e:
            logger.error(
                "event_classification_sync_failed",
                error=str(e),
                event_id=event_id,
            )
            raise TimelineServiceError(f"Failed to update event classification: {e}")

    async def get_unclassified_events(
        self,
        matter_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> UnclassifiedEventsResponse:
        """Get events needing manual classification.

        Returns events where:
        - event_type = 'raw_date' OR 'unclassified'
        - OR confidence < 0.7

        Args:
            matter_id: Matter UUID.
            page: Page number.
            per_page: Items per page.

        Returns:
            UnclassifiedEventsResponse with paginated events.
        """
        def _query():
            # Use OR filter for multiple conditions
            return (
                self.client.table("events")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
                .or_("event_type.eq.raw_date,event_type.eq.unclassified,confidence.lt.0.7")
                .order("event_date", desc=False)
                .range((page - 1) * per_page, page * per_page - 1)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_query)

            items = [
                self._db_row_to_unclassified_item(row)
                for row in (response.data or [])
            ]

            total = response.count or 0
            total_pages = ceil(total / per_page) if per_page > 0 else 0

            return UnclassifiedEventsResponse(
                data=items,
                meta=PaginationMeta(
                    total=total,
                    page=page,
                    per_page=per_page,
                    total_pages=total_pages,
                ),
            )

        except Exception as e:
            logger.error(
                "get_unclassified_events_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise TimelineServiceError(f"Failed to get unclassified events: {e}")

    async def get_events_for_classification(
        self,
        matter_id: str,
        limit: int = 100,
    ) -> list[RawEvent]:
        """Get raw_date events ready for classification.

        Args:
            matter_id: Matter UUID.
            limit: Maximum events to return.

        Returns:
            List of RawEvent objects with event_type='raw_date'.
        """
        def _query():
            return (
                self.client.table("events")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
                .order("event_date", desc=False)
                .limit(limit)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_query)

            if response.data:
                return [self._db_row_to_raw_event(row) for row in response.data]
            return []

        except Exception as e:
            logger.error(
                "get_events_for_classification_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise TimelineServiceError(f"Failed to get events for classification: {e}")

    def get_events_for_classification_sync(
        self,
        matter_id: str,
        limit: int = 100,
        document_id: str | None = None,
    ) -> list[RawEvent]:
        """Synchronous version for Celery tasks.

        Args:
            matter_id: Matter UUID.
            limit: Maximum events to return.
            document_id: Optional filter to specific document.

        Returns:
            List of RawEvent objects.
        """
        try:
            query = (
                self.client.table("events")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
            )

            # Apply document filter if provided (Issue #3 fix)
            if document_id:
                query = query.eq("document_id", document_id)

            response = (
                query
                .order("event_date", desc=False)
                .limit(limit)
                .execute()
            )

            if response.data:
                return [self._db_row_to_raw_event(row) for row in response.data]
            return []

        except Exception as e:
            logger.error(
                "get_events_for_classification_sync_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise TimelineServiceError(f"Failed to get events for classification: {e}")

    def get_all_events_for_reclassification_sync(
        self,
        matter_id: str,
        limit: int = 10000,
    ) -> list[RawEvent]:
        """Get ALL events for reclassification (force_reclassify mode).

        Unlike get_events_for_classification_sync which only returns raw_date events,
        this returns all events regardless of current type for re-classification.

        Args:
            matter_id: Matter UUID.
            limit: Maximum events to return.

        Returns:
            List of RawEvent objects (all types, not just raw_date).
        """
        try:
            response = (
                self.client.table("events")
                .select("*")
                .eq("matter_id", matter_id)
                .order("event_date", desc=False)
                .limit(limit)
                .execute()
            )

            if response.data:
                return [self._db_row_to_raw_event(row) for row in response.data]
            return []

        except Exception as e:
            logger.error(
                "get_all_events_for_reclassification_sync_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise TimelineServiceError(f"Failed to get events for reclassification: {e}")

    async def bulk_update_classifications(
        self,
        classifications: list[EventClassificationResult],
        matter_id: str,
    ) -> int:
        """Update multiple events with classification results.

        Args:
            classifications: List of classification results.
            matter_id: Matter UUID for validation.

        Returns:
            Number of successfully updated events.

        Raises:
            TimelineServiceError: If bulk update fails.
        """
        if not classifications:
            return 0

        updated_count = 0

        for result in classifications:
            try:
                success = await self.update_event_classification(
                    event_id=result.event_id,
                    matter_id=matter_id,
                    event_type=result.event_type.value,
                    confidence=result.classification_confidence,
                )
                if success:
                    updated_count += 1

            except Exception as e:
                logger.warning(
                    "bulk_classification_item_failed",
                    event_id=result.event_id,
                    error=str(e),
                )
                continue

        logger.info(
            "bulk_classifications_updated",
            matter_id=matter_id,
            total=len(classifications),
            updated=updated_count,
        )

        return updated_count

    def bulk_update_classifications_sync(
        self,
        classifications: list[EventClassificationResult],
        matter_id: str,
    ) -> int:
        """Synchronous bulk update for Celery tasks.

        Args:
            classifications: List of classification results.
            matter_id: Matter UUID.

        Returns:
            Number of successfully updated events.
        """
        if not classifications:
            return 0

        updated_count = 0

        for result in classifications:
            try:
                success = self.update_event_classification_sync(
                    event_id=result.event_id,
                    matter_id=matter_id,
                    event_type=result.event_type.value,
                    confidence=result.classification_confidence,
                )
                if success:
                    updated_count += 1

            except Exception as e:
                logger.warning(
                    "bulk_classification_sync_item_failed",
                    event_id=result.event_id,
                    error=str(e),
                )
                continue

        logger.info(
            "bulk_classifications_updated_sync",
            matter_id=matter_id,
            total=len(classifications),
            updated=updated_count,
        )

        return updated_count

    async def get_classified_events(
        self,
        matter_id: str,
        event_type: str | None = None,
        confidence_min: float | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> ClassifiedEventsListResponse:
        """Get classified events for a matter.

        Returns events where event_type is NOT 'raw_date'.

        Args:
            matter_id: Matter UUID.
            event_type: Optional filter by event type.
            confidence_min: Optional minimum confidence filter.
            page: Page number.
            per_page: Items per page.

        Returns:
            ClassifiedEventsListResponse with paginated events.
        """
        def _query():
            query = (
                self.client.table("events")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
                .neq("event_type", "raw_date")
            )

            if event_type:
                query = query.eq("event_type", event_type)

            if confidence_min is not None:
                query = query.gte("confidence", confidence_min)

            query = query.order("event_date", desc=False)

            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            return query.execute()

        try:
            response = await asyncio.to_thread(_query)

            items = [
                self._db_row_to_classification_list_item(row)
                for row in (response.data or [])
            ]

            total = response.count or 0
            total_pages = ceil(total / per_page) if per_page > 0 else 0

            return ClassifiedEventsListResponse(
                data=items,
                meta=PaginationMeta(
                    total=total,
                    page=page,
                    per_page=per_page,
                    total_pages=total_pages,
                ),
            )

        except Exception as e:
            logger.error(
                "get_classified_events_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise TimelineServiceError(f"Failed to get classified events: {e}")

    async def update_manual_classification(
        self,
        event_id: str,
        matter_id: str,
        event_type: EventType,
    ) -> ClassifiedEvent | None:
        """Update event with manual classification.

        Sets is_manual=True and confidence=1.0 (human verified).

        Args:
            event_id: Event UUID.
            matter_id: Matter UUID.
            event_type: New event type.

        Returns:
            Updated ClassifiedEvent or None if not found.
        """
        def _update():
            return (
                self.client.table("events")
                .update({
                    "event_type": event_type.value,
                    "confidence": 1.0,  # Human verified
                    "is_manual": True,
                })
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .select()
                .execute()
            )

        try:
            response = await asyncio.to_thread(_update)

            if response.data:
                row = response.data[0]
                logger.info(
                    "manual_classification_updated",
                    event_id=event_id,
                    event_type=event_type.value,
                )
                return self._db_row_to_classified_event(row)

            logger.warning(
                "manual_classification_not_found",
                event_id=event_id,
                matter_id=matter_id,
            )
            return None

        except Exception as e:
            logger.error(
                "manual_classification_failed",
                error=str(e),
                event_id=event_id,
            )
            raise TimelineServiceError(f"Failed to update manual classification: {e}")

    async def count_events_for_classification(
        self,
        matter_id: str,
        document_ids: list[str] | None = None,
    ) -> int:
        """Count raw_date events needing classification.

        Args:
            matter_id: Matter UUID.
            document_ids: Optional filter to specific documents.

        Returns:
            Count of events with event_type='raw_date'.
        """
        def _query():
            query = (
                self.client.table("events")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
            )

            if document_ids:
                query = query.in_("document_id", document_ids)

            return query.limit(1).execute()

        try:
            response = await asyncio.to_thread(_query)
            return response.count or 0

        except Exception as e:
            logger.error(
                "count_events_for_classification_failed",
                error=str(e),
                matter_id=matter_id,
            )
            return 0

    def count_events_for_classification_sync(
        self,
        matter_id: str,
        document_ids: list[str] | None = None,
    ) -> int:
        """Synchronous count for Celery tasks.

        Args:
            matter_id: Matter UUID.
            document_ids: Optional filter to specific documents.

        Returns:
            Count of raw_date events.
        """
        try:
            query = (
                self.client.table("events")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("event_type", "raw_date")
            )

            if document_ids:
                query = query.in_("document_id", document_ids)

            response = query.limit(1).execute()
            return response.count or 0

        except Exception:
            return 0

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
        from datetime import date, datetime

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

    def _db_row_to_classification_list_item(self, row: dict) -> EventClassificationListItem:
        """Convert database row to classification list item."""
        from datetime import date

        event_date = row.get("event_date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)

        # Extract clean description
        description = row.get("description", "")
        _, _, clean_description = self._parse_ambiguity_from_description(description)

        return EventClassificationListItem(
            id=row["id"],
            event_date=event_date,
            event_date_precision=row.get("event_date_precision", "day"),
            event_date_text=row.get("event_date_text"),
            event_type=row.get("event_type", "unclassified"),
            description=clean_description,
            classification_confidence=row.get("confidence", 0.8),
            document_id=row.get("document_id"),
            source_page=row.get("source_page"),
            verified=row.get("is_manual", False),
        )

    def _db_row_to_unclassified_item(self, row: dict) -> UnclassifiedEventItem:
        """Convert database row to unclassified event item."""
        from datetime import date

        event_date = row.get("event_date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)

        # Extract clean description
        description = row.get("description", "")
        _, _, clean_description = self._parse_ambiguity_from_description(description)

        # Generate suggested_types based on event type and confidence
        # For unclassified events, provide helpful suggestions
        suggested_types = []
        event_type = row.get("event_type", "unclassified")
        confidence = row.get("confidence", 0.0)

        # If this was classified but with low confidence, suggest alternatives
        if event_type not in ("raw_date", "unclassified") and confidence < 0.7:
            # The actual classified type is still the best guess
            suggested_types.append({
                "type": event_type,
                "confidence": confidence,
            })

        return UnclassifiedEventItem(
            id=row["id"],
            event_date=event_date,
            event_type=event_type,
            description=clean_description,
            classification_confidence=confidence,
            suggested_types=suggested_types,
            document_id=row.get("document_id"),
        )

    def _db_row_to_classified_event(self, row: dict) -> ClassifiedEvent:
        """Convert database row to ClassifiedEvent model."""
        from datetime import date, datetime

        event_date = row.get("event_date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)

        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        # Extract clean description
        description = row.get("description", "")
        _, _, clean_description = self._parse_ambiguity_from_description(description)

        # Parse event type
        raw_type = row.get("event_type", "unclassified")
        try:
            event_type = EventType(raw_type)
        except ValueError:
            event_type = EventType.UNCLASSIFIED

        return ClassifiedEvent(
            id=row["id"],
            matter_id=row["matter_id"],
            document_id=row.get("document_id"),
            event_date=event_date,
            event_date_precision=row.get("event_date_precision", "day"),
            event_date_text=row.get("event_date_text"),
            event_type=event_type,
            description=clean_description,
            classification_confidence=row.get("confidence", 0.8),
            source_page=row.get("source_page"),
            source_bbox_ids=row.get("source_bbox_ids") or [],
            verified=row.get("is_manual", False),
            is_manual=row.get("is_manual", False),
            created_at=created_at,
            updated_at=updated_at,
        )

    # =========================================================================
    # Entity Linking Methods (Story 4-3)
    # =========================================================================

    async def update_event_entities(
        self,
        event_id: str,
        matter_id: str,
        entity_ids: list[str],
    ) -> bool:
        """Update entities linked to an event.

        Args:
            event_id: Event UUID.
            matter_id: Matter UUID for validation.
            entity_ids: List of entity UUIDs to link.

        Returns:
            True if update succeeded.
        """
        def _update():
            return (
                self.client.table("events")
                .update({"entities_involved": entity_ids})
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_update)

            if response.data:
                logger.debug(
                    "event_entities_updated",
                    event_id=event_id,
                    entity_count=len(entity_ids),
                )
                return True
            return False

        except Exception as e:
            logger.error(
                "event_entities_update_failed",
                event_id=event_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to update event entities: {e}")

    def update_event_entities_sync(
        self,
        event_id: str,
        matter_id: str,
        entity_ids: list[str],
    ) -> bool:
        """Synchronous version for Celery tasks.

        Args:
            event_id: Event UUID.
            matter_id: Matter UUID.
            entity_ids: List of entity UUIDs.

        Returns:
            True if update succeeded.
        """
        try:
            response = (
                self.client.table("events")
                .update({"entities_involved": entity_ids})
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .execute()
            )

            if response.data:
                logger.debug(
                    "event_entities_updated_sync",
                    event_id=event_id,
                    entity_count=len(entity_ids),
                )
                return True
            return False

        except Exception as e:
            logger.error(
                "event_entities_update_sync_failed",
                event_id=event_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to update event entities: {e}")

    async def bulk_update_event_entities(
        self,
        event_entities: dict[str, list[str]],
        matter_id: str,
    ) -> int:
        """Bulk update entities for multiple events.

        Args:
            event_entities: Dict mapping event_id to list of entity_ids.
            matter_id: Matter UUID for validation.

        Returns:
            Number of successfully updated events.
        """
        if not event_entities:
            return 0

        updated_count = 0

        for event_id, entity_ids in event_entities.items():
            try:
                success = await self.update_event_entities(
                    event_id=event_id,
                    matter_id=matter_id,
                    entity_ids=entity_ids,
                )
                if success:
                    updated_count += 1
            except Exception as e:
                logger.warning(
                    "bulk_entity_update_item_failed",
                    event_id=event_id,
                    error=str(e),
                )
                continue

        logger.info(
            "bulk_entity_update_complete",
            matter_id=matter_id,
            total=len(event_entities),
            updated=updated_count,
        )

        return updated_count

    def bulk_update_event_entities_sync(
        self,
        event_entities: dict[str, list[str]],
        matter_id: str,
    ) -> int:
        """Synchronous bulk update for Celery tasks.

        Args:
            event_entities: Dict mapping event_id to list of entity_ids.
            matter_id: Matter UUID.

        Returns:
            Number of successfully updated events.
        """
        if not event_entities:
            return 0

        updated_count = 0

        for event_id, entity_ids in event_entities.items():
            try:
                success = self.update_event_entities_sync(
                    event_id=event_id,
                    matter_id=matter_id,
                    entity_ids=entity_ids,
                )
                if success:
                    updated_count += 1
            except Exception as e:
                logger.warning(
                    "bulk_entity_update_sync_item_failed",
                    event_id=event_id,
                    error=str(e),
                )
                continue

        logger.info(
            "bulk_entity_update_sync_complete",
            matter_id=matter_id,
            total=len(event_entities),
            updated=updated_count,
        )

        return updated_count

    async def get_events_for_entity_linking(
        self,
        matter_id: str,
        limit: int = 100,
    ) -> list[RawEvent]:
        """Get events that need entity linking.

        Returns events where entities_involved is empty/null.

        Args:
            matter_id: Matter UUID.
            limit: Maximum events to return.

        Returns:
            List of RawEvent objects without entity links.
        """
        def _query():
            return (
                self.client.table("events")
                .select("*")
                .eq("matter_id", matter_id)
                .or_("entities_involved.is.null,entities_involved.eq.{}")
                .order("event_date", desc=False)
                .limit(limit)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_query)

            if response.data:
                return [self._db_row_to_raw_event(row) for row in response.data]
            return []

        except Exception as e:
            logger.error(
                "get_events_for_entity_linking_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to get events for entity linking: {e}")

    def get_events_for_entity_linking_sync(
        self,
        matter_id: str,
        limit: int = 100,
    ) -> list[RawEvent]:
        """Synchronous version for Celery tasks.

        Args:
            matter_id: Matter UUID.
            limit: Maximum events to return.

        Returns:
            List of RawEvent objects without entity links.
        """
        try:
            response = (
                self.client.table("events")
                .select("*")
                .eq("matter_id", matter_id)
                .or_("entities_involved.is.null,entities_involved.eq.{}")
                .order("event_date", desc=False)
                .limit(limit)
                .execute()
            )

            if response.data:
                return [self._db_row_to_raw_event(row) for row in response.data]
            return []

        except Exception as e:
            logger.error(
                "get_events_for_entity_linking_sync_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to get events for entity linking: {e}")

    async def get_events_by_entity(
        self,
        entity_id: str,
        matter_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> RawDatesListResponse:
        """Get events involving a specific entity.

        Args:
            entity_id: Entity UUID to filter by.
            matter_id: Matter UUID for validation.
            page: Page number.
            per_page: Items per page.

        Returns:
            RawDatesListResponse with events involving the entity.
        """
        def _query():
            return (
                self.client.table("events")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
                .contains("entities_involved", [entity_id])
                .order("event_date", desc=False)
                .range((page - 1) * per_page, page * per_page - 1)
                .execute()
            )

        try:
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

        except Exception as e:
            logger.error(
                "get_events_by_entity_failed",
                entity_id=entity_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to get events by entity: {e}")

    async def count_events_for_entity_linking(
        self,
        matter_id: str,
    ) -> int:
        """Count events needing entity linking.

        Args:
            matter_id: Matter UUID.

        Returns:
            Count of events without entity links.
        """
        def _query():
            return (
                self.client.table("events")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .or_("entities_involved.is.null,entities_involved.eq.{}")
                .limit(1)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_query)
            return response.count or 0

        except Exception as e:
            logger.error(
                "count_events_for_entity_linking_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return 0

    # =========================================================================
    # Manual Event CRUD Methods (Story 10B.5)
    # =========================================================================

    async def create_manual_event(
        self,
        matter_id: str,
        user_id: str,
        request: ManualEventCreateRequest,
    ) -> ManualEventResponse:
        """Create a manual timeline event.

        Args:
            matter_id: Matter UUID.
            user_id: Creator user UUID.
            request: Manual event creation request.

        Returns:
            ManualEventResponse with created event.

        Raises:
            TimelineServiceError: If creation fails.
        """
        # Combine title and description for the description field
        description = request.title
        if request.description:
            description = f"{request.title}\n\n{request.description}"

        event_record = {
            "matter_id": matter_id,
            "document_id": request.source_document_id,
            "event_date": request.event_date.isoformat(),
            "event_date_precision": "day",  # Manual events always have day precision
            "event_date_text": None,  # No original text for manual events
            "event_type": request.event_type.value,
            "description": description[:5000],
            "entities_involved": request.entity_ids if request.entity_ids else [],
            "source_page": request.source_page,
            "source_bbox_ids": [],
            "confidence": 1.0,  # Manual events have 100% confidence
            "is_manual": True,
            "created_by": user_id,
        }

        def _insert():
            return (
                self.client.table("events")
                .insert(event_record)
                .select()
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                row = response.data[0]
                logger.info(
                    "manual_event_created",
                    matter_id=matter_id,
                    event_id=row["id"],
                    user_id=user_id,
                )
                return self._db_row_to_manual_event_response(row)

            raise TimelineServiceError("Failed to create manual event - no data returned")

        except TimelineServiceError:
            raise
        except Exception as e:
            logger.error(
                "manual_event_creation_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise TimelineServiceError(f"Failed to create manual event: {e}")

    async def update_manual_event(
        self,
        event_id: str,
        matter_id: str,
        request: ManualEventUpdateRequest,
    ) -> ManualEventResponse | None:
        """Update a timeline event.

        For manual events: all provided fields are updated.
        For auto-extracted events: only event_type is updated (classification correction).

        Args:
            event_id: Event UUID.
            matter_id: Matter UUID.
            request: Update request with fields to change.

        Returns:
            ManualEventResponse with updated event, or None if not found.

        Raises:
            TimelineServiceError: If update fails.
        """
        # First, get the existing event to check if it's manual
        existing = await self.get_event_by_id(event_id, matter_id)
        if not existing:
            return None

        # Build update dict based on whether event is manual
        update_data: dict = {}

        if existing.is_manual:
            # Manual event: allow updating all fields
            if request.event_date is not None:
                update_data["event_date"] = request.event_date.isoformat()
            if request.event_type is not None:
                update_data["event_type"] = request.event_type.value
            if request.title is not None:
                description = request.title
                if request.description is not None:
                    description = f"{request.title}\n\n{request.description}"
                elif existing.description:
                    # Keep existing description if only title is updated
                    parts = existing.description.split("\n\n", 1)
                    if len(parts) > 1:
                        description = f"{request.title}\n\n{parts[1]}"
                update_data["description"] = description[:5000]
            elif request.description is not None:
                # Only description updated, keep title
                parts = existing.description.split("\n\n", 1)
                title = parts[0] if parts else ""
                update_data["description"] = f"{title}\n\n{request.description}"[:5000]
            if request.entity_ids is not None:
                update_data["entities_involved"] = request.entity_ids
        else:
            # Auto-extracted event: only allow event_type update (classification correction)
            if request.event_type is not None:
                update_data["event_type"] = request.event_type.value
                update_data["is_manual"] = True  # Mark as manually classified
                update_data["confidence"] = 1.0  # Human verified

        if not update_data:
            # Nothing to update, return existing
            return self._db_row_to_manual_event_response_from_raw_event(existing)

        def _update():
            return (
                self.client.table("events")
                .update(update_data)
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .select()
                .execute()
            )

        try:
            response = await asyncio.to_thread(_update)

            if response.data:
                row = response.data[0]
                logger.info(
                    "manual_event_updated",
                    event_id=event_id,
                    matter_id=matter_id,
                    updated_fields=list(update_data.keys()),
                )
                return self._db_row_to_manual_event_response(row)

            return None

        except Exception as e:
            logger.error(
                "manual_event_update_failed",
                event_id=event_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to update manual event: {e}")

    async def delete_manual_event(
        self,
        event_id: str,
        matter_id: str,
    ) -> bool:
        """Delete a manual timeline event.

        Only manual events can be deleted. Auto-extracted events
        cannot be deleted.

        Args:
            event_id: Event UUID.
            matter_id: Matter UUID.

        Returns:
            True if deleted, False if event not found or not manual.

        Raises:
            TimelineServiceError: If deletion fails or event is not manual.
        """
        # First check if event exists and is manual
        existing = await self.get_event_by_id(event_id, matter_id)
        if not existing:
            return False

        if not existing.is_manual:
            raise TimelineServiceError(
                "Cannot delete auto-extracted events. Only manual events can be deleted.",
                code="CANNOT_DELETE_AUTO_EVENT",
            )

        def _delete():
            return (
                self.client.table("events")
                .delete()
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .eq("is_manual", True)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_delete)

            deleted = bool(response.data)
            if deleted:
                logger.info(
                    "manual_event_deleted",
                    event_id=event_id,
                    matter_id=matter_id,
                )
            return deleted

        except Exception as e:
            logger.error(
                "manual_event_delete_failed",
                event_id=event_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to delete manual event: {e}")

    async def set_event_verification(
        self,
        event_id: str,
        matter_id: str,
        is_verified: bool,
    ) -> ManualEventResponse | None:
        """Set the verification status of an event.

        Args:
            event_id: Event UUID.
            matter_id: Matter UUID.
            is_verified: Whether event is verified.

        Returns:
            ManualEventResponse with updated event, or None if not found.
        """
        def _update():
            return (
                self.client.table("events")
                .update({"is_manual": is_verified})  # is_manual serves as verified flag
                .eq("id", event_id)
                .eq("matter_id", matter_id)
                .select()
                .execute()
            )

        try:
            response = await asyncio.to_thread(_update)

            if response.data:
                row = response.data[0]
                logger.info(
                    "event_verification_updated",
                    event_id=event_id,
                    is_verified=is_verified,
                )
                return self._db_row_to_manual_event_response(row)

            return None

        except Exception as e:
            logger.error(
                "event_verification_update_failed",
                event_id=event_id,
                error=str(e),
            )
            raise TimelineServiceError(f"Failed to update event verification: {e}")

    def _db_row_to_manual_event_response(self, row: dict) -> ManualEventResponse:
        """Convert database row to ManualEventResponse."""
        from datetime import date, datetime

        event_date = row.get("event_date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)

        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        # Extract clean description
        description = row.get("description", "")
        _, _, clean_description = self._parse_ambiguity_from_description(description)

        # Build entity references (we don't have full entity data here, just IDs)
        entities = []
        entity_ids = row.get("entities_involved") or []
        for entity_id in entity_ids:
            entities.append(
                EntityReference(
                    entity_id=entity_id,
                    canonical_name="",  # Would need join to get actual name
                    entity_type="",  # Would need join to get actual type
                    role=None,
                )
            )

        return ManualEventResponse(
            id=row["id"],
            event_date=event_date,
            event_date_precision=row.get("event_date_precision", "day"),
            event_date_text=row.get("event_date_text"),
            event_type=row.get("event_type", "unclassified"),
            description=clean_description,
            document_id=row.get("document_id"),
            source_page=row.get("source_page"),
            confidence=row.get("confidence", 1.0),
            entities=entities,
            is_ambiguous=False,  # Manual events are not ambiguous
            is_verified=row.get("is_manual", False),  # is_manual serves as verified
            is_manual=row.get("is_manual", False),
            created_by=row.get("created_by"),
            created_at=created_at,
        )

    def _db_row_to_manual_event_response_from_raw_event(
        self, event: RawEvent
    ) -> ManualEventResponse:
        """Convert RawEvent to ManualEventResponse."""
        entities = []
        for entity_id in event.entities_involved:
            entities.append(
                EntityReference(
                    entity_id=entity_id,
                    canonical_name="",
                    entity_type="",
                    role=None,
                )
            )

        return ManualEventResponse(
            id=event.id,
            event_date=event.event_date,
            event_date_precision=event.event_date_precision,
            event_date_text=event.event_date_text,
            event_type=event.event_type,
            description=event.description,
            document_id=event.document_id,
            source_page=event.source_page,
            confidence=event.confidence,
            entities=entities,
            is_ambiguous=event.is_ambiguous,
            is_verified=event.is_manual,
            is_manual=event.is_manual,
            created_by=event.created_by,
            created_at=event.created_at,
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
