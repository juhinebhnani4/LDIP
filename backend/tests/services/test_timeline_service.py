"""Tests for Timeline Service.

Story 4-1: Date Extraction with Gemini
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.timeline import (
    ExtractedDate,
    RawDatesListResponse,
    RawEvent,
)
from app.services.timeline_service import (
    TimelineService,
    TimelineServiceError,
    get_timeline_service,
)


class TestTimelineServiceInit:
    """Tests for TimelineService initialization."""

    def test_init_creates_instance(self) -> None:
        """Should create TimelineService instance."""
        service = TimelineService()
        assert service is not None
        assert service._client is None  # Lazy initialization

    def test_singleton_factory(self) -> None:
        """Should return singleton from factory."""
        # Clear cache
        get_timeline_service.cache_clear()

        service1 = get_timeline_service()
        service2 = get_timeline_service()

        assert service1 is service2

        # Clean up
        get_timeline_service.cache_clear()


class TestSaveExtractedDates:
    """Tests for saving extracted dates."""

    @pytest.mark.asyncio
    async def test_save_empty_dates_list(self) -> None:
        """Should return empty list for empty dates."""
        service = TimelineService()

        result = await service.save_extracted_dates(
            matter_id="matter-123",
            document_id="doc-456",
            dates=[],
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_save_dates_creates_events(self) -> None:
        """Should create event records for extracted dates."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "event-1"},
            {"id": "event-2"},
        ]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        service._client = mock_client

        dates = [
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                context_before="Filed on",
                context_after="in court",
                confidence=0.95,
            ),
            ExtractedDate(
                extracted_date=date(2024, 3, 1),
                date_text="March 2024",
                date_precision="month",
                confidence=0.90,
            ),
        ]

        result = await service.save_extracted_dates(
            matter_id="matter-123",
            document_id="doc-456",
            dates=dates,
        )

        assert len(result) == 2
        assert "event-1" in result
        assert "event-2" in result

        # Verify insert was called with correct structure
        mock_client.table.assert_called_with("events")
        insert_call = mock_client.table.return_value.insert
        assert insert_call.called

    def test_save_dates_sync(self) -> None:
        """Should save dates synchronously."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": "event-1"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        service._client = mock_client

        dates = [
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                confidence=0.95,
            ),
        ]

        result = service.save_extracted_dates_sync(
            matter_id="matter-123",
            document_id="doc-456",
            dates=dates,
        )

        assert len(result) == 1
        assert result[0] == "event-1"


class TestGetRawDates:
    """Tests for retrieving raw dates."""

    @pytest.mark.asyncio
    async def test_get_raw_dates_for_document(self) -> None:
        """Should get dates for specific document."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "event-1",
                "matter_id": "matter-123",
                "document_id": "doc-456",
                "event_date": "2024-01-15",
                "event_date_precision": "day",
                "event_date_text": "15/01/2024",
                "event_type": "raw_date",
                "description": "Filed on [15/01/2024] in court",
                "source_page": 1,
                "source_bbox_ids": [],
                "confidence": 0.95,
                "is_manual": False,
                "created_at": "2024-01-20T10:00:00Z",
                "updated_at": "2024-01-20T10:00:00Z",
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = await service.get_raw_dates_for_document(
            document_id="doc-456",
            matter_id="matter-123",
        )

        assert len(result) == 1
        assert result[0].id == "event-1"
        assert result[0].event_date == date(2024, 1, 15)

    @pytest.mark.asyncio
    async def test_get_timeline_for_matter(self) -> None:
        """Should get all timeline events for matter."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "event-1",
                "event_date": "2024-01-15",
                "event_date_precision": "day",
                "event_date_text": "15/01/2024",
                "description": "Filing date",
                "document_id": "doc-456",
                "source_page": 1,
                "confidence": 0.95,
            }
        ]
        mock_response.count = 1
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = await service.get_timeline_for_matter(
            matter_id="matter-123",
            page=1,
            per_page=20,
        )

        assert isinstance(result, RawDatesListResponse)
        assert len(result.data) == 1
        assert result.meta.total == 1

    @pytest.mark.asyncio
    async def test_get_event_by_id(self) -> None:
        """Should get single event by ID."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "event-1",
                "matter_id": "matter-123",
                "document_id": "doc-456",
                "event_date": "2024-01-15",
                "event_date_precision": "day",
                "event_date_text": "15/01/2024",
                "event_type": "raw_date",
                "description": "Filing date",
                "source_page": 1,
                "source_bbox_ids": [],
                "confidence": 0.95,
                "is_manual": False,
                "created_at": "2024-01-20T10:00:00Z",
                "updated_at": "2024-01-20T10:00:00Z",
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = await service.get_event_by_id(
            event_id="event-1",
            matter_id="matter-123",
        )

        assert result is not None
        assert result.id == "event-1"
        assert result.event_date == date(2024, 1, 15)

    @pytest.mark.asyncio
    async def test_get_event_not_found(self) -> None:
        """Should return None for non-existent event."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = await service.get_event_by_id(
            event_id="non-existent",
            matter_id="matter-123",
        )

        assert result is None


class TestDeleteRawDates:
    """Tests for deleting raw dates."""

    @pytest.mark.asyncio
    async def test_delete_dates_for_document(self) -> None:
        """Should delete all raw dates for document."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": "event-1"}, {"id": "event-2"}]
        mock_client.table.return_value.delete.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        service._client = mock_client

        count = await service.delete_raw_dates_for_document(
            document_id="doc-456",
            matter_id="matter-123",
        )

        assert count == 2


class TestHasDatesForDocument:
    """Tests for checking existing dates."""

    @pytest.mark.asyncio
    async def test_has_dates_true(self) -> None:
        """Should return True when dates exist."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.count = 5
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = await service.has_dates_for_document(
            document_id="doc-456",
            matter_id="matter-123",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_has_dates_false(self) -> None:
        """Should return False when no dates exist."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.count = 0
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = await service.has_dates_for_document(
            document_id="doc-456",
            matter_id="matter-123",
        )

        assert result is False

    def test_has_dates_sync(self) -> None:
        """Should check dates synchronously."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.count = 3
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = service.has_dates_for_document_sync(
            document_id="doc-456",
            matter_id="matter-123",
        )

        assert result is True


class TestDescriptionGeneration:
    """Tests for context description generation."""

    @pytest.mark.asyncio
    async def test_description_combines_context(self) -> None:
        """Should combine before/after context with date."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": "event-1"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        service._client = mock_client

        dates = [
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                context_before="The complaint was filed on",
                context_after="before the Honorable Court.",
                confidence=0.95,
            ),
        ]

        await service.save_extracted_dates(
            matter_id="matter-123",
            document_id="doc-456",
            dates=dates,
        )

        # Verify the insert call
        insert_call = mock_client.table.return_value.insert
        insert_args = insert_call.call_args[0][0]
        description = insert_args[0]["description"]

        assert "complaint was filed on" in description
        assert "[15/01/2024]" in description
        assert "Honorable Court" in description


class TestAmbiguityPersistence:
    """Tests for ambiguity data encoding and decoding in descriptions."""

    @pytest.mark.asyncio
    async def test_ambiguous_date_saved_with_marker(self) -> None:
        """Should encode ambiguity info in description."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": "event-1"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        service._client = mock_client

        dates = [
            ExtractedDate(
                extracted_date=date(2024, 2, 1),
                date_text="01/02/2024",
                date_precision="day",
                context_before="Notice dated",
                context_after="was issued.",
                confidence=0.70,
                is_ambiguous=True,
                ambiguity_reason="DD/MM vs MM/DD uncertain",
            ),
        ]

        await service.save_extracted_dates(
            matter_id="matter-123",
            document_id="doc-456",
            dates=dates,
        )

        # Verify the insert call has ambiguity marker
        insert_call = mock_client.table.return_value.insert
        insert_args = insert_call.call_args[0][0]
        description = insert_args[0]["description"]

        assert description.startswith("[AMBIGUOUS:")
        assert "DD/MM vs MM/DD uncertain" in description
        assert "[01/02/2024]" in description

    @pytest.mark.asyncio
    async def test_ambiguous_date_without_reason(self) -> None:
        """Should encode ambiguity even without reason."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": "event-1"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        service._client = mock_client

        dates = [
            ExtractedDate(
                extracted_date=date(2024, 2, 1),
                date_text="01/02/2024",
                date_precision="day",
                confidence=0.70,
                is_ambiguous=True,
                ambiguity_reason=None,
            ),
        ]

        await service.save_extracted_dates(
            matter_id="matter-123",
            document_id="doc-456",
            dates=dates,
        )

        insert_call = mock_client.table.return_value.insert
        insert_args = insert_call.call_args[0][0]
        description = insert_args[0]["description"]

        assert description.startswith("[AMBIGUOUS]")

    def test_parse_ambiguity_from_description_with_reason(self) -> None:
        """Should parse ambiguity marker with reason from description."""
        service = TimelineService()

        description = "[AMBIGUOUS: DD/MM vs MM/DD uncertain] Notice dated [01/02/2024] was issued."

        is_ambiguous, reason, clean = service._parse_ambiguity_from_description(description)

        assert is_ambiguous is True
        assert reason == "DD/MM vs MM/DD uncertain"
        assert clean == "Notice dated [01/02/2024] was issued."

    def test_parse_ambiguity_from_description_without_reason(self) -> None:
        """Should parse ambiguity marker without reason."""
        service = TimelineService()

        description = "[AMBIGUOUS] Notice dated [01/02/2024] was issued."

        is_ambiguous, reason, clean = service._parse_ambiguity_from_description(description)

        assert is_ambiguous is True
        assert reason is None
        assert clean == "Notice dated [01/02/2024] was issued."

    def test_parse_non_ambiguous_description(self) -> None:
        """Should return non-ambiguous for normal descriptions."""
        service = TimelineService()

        description = "Notice dated [01/02/2024] was issued."

        is_ambiguous, reason, clean = service._parse_ambiguity_from_description(description)

        assert is_ambiguous is False
        assert reason is None
        assert clean == description

    def test_parse_empty_description(self) -> None:
        """Should handle empty descriptions."""
        service = TimelineService()

        is_ambiguous, reason, clean = service._parse_ambiguity_from_description("")

        assert is_ambiguous is False
        assert reason is None
        assert clean == ""

    @pytest.mark.asyncio
    async def test_retrieved_event_has_ambiguity_parsed(self) -> None:
        """Should parse ambiguity when retrieving events."""
        service = TimelineService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "event-1",
                "matter_id": "matter-123",
                "document_id": "doc-456",
                "event_date": "2024-02-01",
                "event_date_precision": "day",
                "event_date_text": "01/02/2024",
                "event_type": "raw_date",
                "description": "[AMBIGUOUS: DD/MM vs MM/DD uncertain] Notice dated [01/02/2024] was issued.",
                "source_page": 1,
                "source_bbox_ids": [],
                "confidence": 0.70,
                "is_manual": False,
                "created_at": "2024-01-20T10:00:00Z",
                "updated_at": "2024-01-20T10:00:00Z",
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response
        service._client = mock_client

        result = await service.get_event_by_id(
            event_id="event-1",
            matter_id="matter-123",
        )

        assert result is not None
        assert result.is_ambiguous is True
        assert result.ambiguity_reason == "DD/MM vs MM/DD uncertain"
        assert result.description == "Notice dated [01/02/2024] was issued."
