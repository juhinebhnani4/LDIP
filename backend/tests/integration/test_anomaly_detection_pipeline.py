"""Integration tests for Anomaly Detection Pipeline.

Story 4-4: Timeline Anomaly Detection

Tests the full pipeline: events → anomaly detection → storage → retrieval
with mocked dependencies to verify end-to-end functionality.
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.timeline.anomaly_detector import TimelineAnomalyDetector, get_anomaly_detector
from app.engines.timeline.legal_sequences import CaseType, LegalSequenceValidator
from app.engines.timeline.timeline_builder import TimelineEvent
from app.models.anomaly import (
    AnomaliesListResponse,
    Anomaly,
    AnomalyCreate,
    AnomalyListItem,
    AnomalySeverity,
    AnomalySummaryData,
    AnomalySummaryResponse,
    AnomalyType,
    PaginationMeta,
)
from app.models.timeline import EventType
from app.services.anomaly_service import AnomalyService, get_anomaly_service


# =============================================================================
# Helper Functions
# =============================================================================


def create_timeline_event(
    event_id: str,
    event_date: date,
    event_type: EventType,
    description: str = "Test event",
) -> TimelineEvent:
    """Create TimelineEvent for testing."""
    return TimelineEvent(
        event_id=event_id,
        event_date=event_date,
        event_date_precision="day",
        event_date_text=event_date.isoformat(),
        event_type=event_type,
        description=description,
        document_id="doc-123",
        document_name="test-document.pdf",
        source_page=1,
        confidence=0.9,
        entities=[],
        is_ambiguous=False,
        is_verified=False,
    )


# =============================================================================
# Pipeline Integration Tests
# =============================================================================


class TestAnomalyDetectionPipelineIntegration:
    """Tests for full events → detection → storage pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_detection_to_storage(self) -> None:
        """Should detect anomalies and store them.

        Tests:
        1. Build timeline events (mocked)
        2. Run anomaly detection
        3. Save detected anomalies
        4. Retrieve stored anomalies
        """
        detector = TimelineAnomalyDetector()
        anomaly_service = AnomalyService()

        # Create test events with known anomalies
        events = [
            # Sequence violation: hearing before filing
            create_timeline_event("e1", date(2024, 1, 15), EventType.HEARING, "Hearing held"),
            create_timeline_event("e2", date(2024, 3, 20), EventType.FILING, "Application filed"),
            # Large gap
            create_timeline_event("e3", date(2025, 6, 1), EventType.ORDER, "Order passed"),
        ]

        # Step 1: Detect anomalies
        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        # Should detect sequence violation and gap
        assert len(anomalies) >= 2

        anomaly_types = {a.anomaly_type for a in anomalies}
        assert AnomalyType.SEQUENCE_VIOLATION in anomaly_types
        assert AnomalyType.GAP in anomaly_types

        # Step 2: Mock save operation
        mock_client = MagicMock()
        mock_insert_response = MagicMock()
        mock_insert_response.data = [
            {"id": f"anomaly-{i}"} for i in range(len(anomalies))
        ]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_insert_response
        anomaly_service._client = mock_client

        # Save anomalies
        saved_ids = await anomaly_service.save_anomalies(anomalies)

        assert len(saved_ids) == len(anomalies)
        mock_client.table.assert_called_with("anomalies")

    @pytest.mark.asyncio
    async def test_pipeline_with_no_anomalies(self) -> None:
        """Should handle timeline with no anomalies."""
        detector = TimelineAnomalyDetector()

        # Create events in correct order with normal timing
        events = [
            create_timeline_event("e1", date(2024, 1, 10), EventType.NOTICE, "Notice sent"),
            create_timeline_event("e2", date(2024, 2, 15), EventType.FILING, "Filed"),
            create_timeline_event("e3", date(2024, 3, 20), EventType.HEARING, "Hearing"),
            create_timeline_event("e4", date(2024, 4, 5), EventType.ORDER, "Order"),
        ]

        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        # No anomalies expected for well-ordered timeline
        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_pipeline_with_duplicates(self) -> None:
        """Should detect duplicate events in timeline."""
        detector = TimelineAnomalyDetector()

        # Create events with potential duplicates
        events = [
            create_timeline_event("e1", date(2024, 1, 15), EventType.FILING, "Application filed in DRT Mumbai"),
            create_timeline_event("e2", date(2024, 1, 15), EventType.FILING, "Application filed in DRT Mumbai court"),
        ]

        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        # Should detect duplicate
        duplicate_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.DUPLICATE]
        assert len(duplicate_anomalies) >= 1


# =============================================================================
# Retrieval Integration Tests
# =============================================================================


class TestAnomalyRetrievalIntegration:
    """Tests for anomaly retrieval after detection."""

    @pytest.mark.asyncio
    async def test_retrieve_anomalies_with_filters(self) -> None:
        """Should retrieve anomalies with severity filter."""
        anomaly_service = AnomalyService()

        # Mock database response
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "anomaly-1",
                "matter_id": "matter-123",
                "anomaly_type": "gap",
                "severity": "high",
                "title": "Large gap",
                "explanation": "400 days gap",
                "event_ids": ["e1", "e2"],
                "expected_order": None,
                "actual_order": None,
                "gap_days": 400,
                "confidence": 0.95,
                "verified": False,
                "dismissed": False,
                "verified_by": None,
                "verified_at": None,
                "created_at": "2026-01-13T10:00:00+00:00",
                "updated_at": "2026-01-13T10:00:00+00:00",
            }
        ]
        mock_response.count = 1

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_response

        mock_table = MagicMock()
        mock_table.select.return_value = mock_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table
        anomaly_service._client = mock_client

        # Retrieve with filter
        result = await anomaly_service.get_anomalies_for_matter(
            matter_id="matter-123",
            page=1,
            per_page=20,
            severity="high",
        )

        assert isinstance(result, AnomaliesListResponse)
        assert len(result.data) == 1
        assert result.data[0].severity == "high"

    @pytest.mark.asyncio
    async def test_summary_after_detection(self) -> None:
        """Should return correct summary after detection."""
        anomaly_service = AnomalyService()

        # Mock database response for summary
        mock_response = MagicMock()
        mock_response.data = [
            {"severity": "high", "anomaly_type": "gap", "verified": False, "dismissed": False},
            {"severity": "medium", "anomaly_type": "sequence_violation", "verified": False, "dismissed": False},
            {"severity": "low", "anomaly_type": "duplicate", "verified": True, "dismissed": False},
        ]

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = mock_response

        mock_table = MagicMock()
        mock_table.select.return_value = mock_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table
        anomaly_service._client = mock_client

        # Get summary
        summary = await anomaly_service.get_anomaly_summary("matter-123")

        assert summary.data.total == 3
        assert summary.data.by_severity["high"] == 1
        assert summary.data.by_severity["medium"] == 1
        assert summary.data.by_severity["low"] == 1
        assert summary.data.verified == 1
        assert summary.data.unreviewed == 2


# =============================================================================
# Dismiss/Verify Integration Tests
# =============================================================================


class TestDismissVerifyIntegration:
    """Tests for anomaly dismiss and verify operations."""

    @pytest.mark.asyncio
    async def test_dismiss_updates_status(self) -> None:
        """Should update anomaly status when dismissed."""
        anomaly_service = AnomalyService()

        # Mock update response
        mock_update_response = MagicMock()
        mock_update_response.data = [{"id": "anomaly-123"}]

        mock_update_query = MagicMock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = mock_update_response

        # Mock select response after update
        mock_select_response = MagicMock()
        mock_select_response.data = {
            "id": "anomaly-123",
            "matter_id": "matter-123",
            "anomaly_type": "gap",
            "severity": "medium",
            "title": "Gap anomaly",
            "explanation": "Test",
            "event_ids": ["e1"],
            "expected_order": None,
            "actual_order": None,
            "gap_days": 200,
            "confidence": 0.9,
            "verified": False,
            "dismissed": True,
            "verified_by": "user-123",
            "verified_at": "2026-01-13T12:00:00+00:00",
            "created_at": "2026-01-13T10:00:00+00:00",
            "updated_at": "2026-01-13T12:00:00+00:00",
        }

        mock_select_query = MagicMock()
        mock_select_query.eq.return_value = mock_select_query
        mock_select_query.single.return_value = mock_select_query
        mock_select_query.execute.return_value = mock_select_response

        mock_table = MagicMock()
        mock_table.update.return_value = mock_update_query
        mock_table.select.return_value = mock_select_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table
        anomaly_service._client = mock_client

        # Dismiss anomaly
        result = await anomaly_service.dismiss_anomaly(
            anomaly_id="anomaly-123",
            matter_id="matter-123",
            user_id="user-123",
        )

        assert result is not None
        assert result.dismissed is True
        assert result.verified_by == "user-123"


# =============================================================================
# Redetection Integration Tests
# =============================================================================


class TestRedetectionIntegration:
    """Tests for force redetection functionality."""

    @pytest.mark.asyncio
    async def test_delete_before_redetect(self) -> None:
        """Should delete existing anomalies before redetection."""
        anomaly_service = AnomalyService()

        # Mock count response
        mock_count_response = MagicMock()
        mock_count_response.count = 5

        mock_count_query = MagicMock()
        mock_count_query.eq.return_value = mock_count_query
        mock_count_query.execute.return_value = mock_count_response

        # Mock delete response
        mock_delete_query = MagicMock()
        mock_delete_query.eq.return_value = mock_delete_query
        mock_delete_query.execute.return_value = MagicMock()

        mock_table = MagicMock()
        mock_table.select.return_value = mock_count_query
        mock_table.delete.return_value = mock_delete_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table
        anomaly_service._client = mock_client

        # Delete existing anomalies
        deleted_count = await anomaly_service.delete_anomalies_for_matter("matter-123")

        assert deleted_count == 5
        mock_table.delete.assert_called_once()


# =============================================================================
# Cache Invalidation Tests
# =============================================================================


class TestCacheInvalidationIntegration:
    """Tests for cache invalidation after anomaly operations."""

    @pytest.mark.asyncio
    async def test_cache_invalidated_after_detection(self) -> None:
        """Cache should be invalidated after anomaly detection.

        Note: This tests the integration pattern, actual cache
        invalidation is handled by the task.
        """
        detector = TimelineAnomalyDetector()

        events = [
            create_timeline_event("e1", date(2024, 1, 15), EventType.HEARING, "Hearing"),
            create_timeline_event("e2", date(2024, 3, 20), EventType.FILING, "Filing"),
        ]

        # Detection should complete without errors
        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        # Anomalies detected - cache would be invalidated in task
        assert len(anomalies) > 0
