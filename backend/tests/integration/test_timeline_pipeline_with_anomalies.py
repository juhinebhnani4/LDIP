"""Integration tests for Timeline Pipeline with Anomaly Auto-Trigger (Story 14-7).

Tests the full pipeline flow: entity linking → anomaly detection auto-triggered.
Verifies job tracking records both stages and anomalies are created.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.timeline.timeline_builder import TimelineEvent
from app.models.anomaly import AnomalyType
from app.models.job import JobType
from app.models.timeline import EventType


def create_mock_timeline_event(
    event_id: str,
    event_date: date,
    event_type: EventType,
    description: str = "Test event",
    entity_ids: list[str] | None = None,
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


class TestFullPipelineEntityLinkingToAnomalyDetection:
    """Tests for full pipeline: entity linking → anomaly detection."""

    @pytest.fixture
    def mock_job_tracker(self) -> MagicMock:
        """Create mock job tracking service."""
        tracker = MagicMock()
        tracker.create_job = AsyncMock(
            return_value=MagicMock(id="linking-job-123")
        )
        tracker.update_job_status = AsyncMock()
        return tracker

    @pytest.fixture
    def mock_timeline_service(self) -> MagicMock:
        """Create mock timeline service with test events."""
        service = MagicMock()

        # Mock event that can have entity links
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Borrower ABC defaulted on loan"
        mock_event.document_id = "doc-123"

        service.get_events_for_entity_linking_sync.return_value = [mock_event]
        service.bulk_update_event_entities_sync.return_value = 1
        return service

    @pytest.fixture
    def mock_mig_service(self) -> MagicMock:
        """Create mock MIG service with test entities."""
        service = MagicMock()

        # Mock entity
        mock_entity = MagicMock()
        mock_entity.id = "entity-1"
        mock_entity.canonical_name = "ABC Corporation"

        service.get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )
        return service

    @pytest.fixture
    def mock_entity_linker(self) -> MagicMock:
        """Create mock entity linker that finds matches."""
        linker = MagicMock()
        linker.link_entities_to_event_sync.return_value = ["entity-1"]
        return linker

    @pytest.fixture
    def mock_cache_service(self) -> MagicMock:
        """Create mock cache service."""
        service = MagicMock()
        service.invalidate_timeline = AsyncMock()
        return service

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_full_flow_entity_linking_triggers_anomaly_detection(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_job_tracker: MagicMock,
        mock_timeline_service: MagicMock,
        mock_mig_service: MagicMock,
        mock_entity_linker: MagicMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Should trigger anomaly detection after entity linking completes.

        Pipeline flow:
        1. Entity linking starts
        2. Entity linking completes successfully
        3. Anomaly detection is automatically queued
        4. Both jobs are tracked
        """
        from app.workers.tasks.engine_tasks import link_entities_for_matter

        # Setup mocks
        mock_get_job_tracker.return_value = mock_job_tracker
        mock_get_timeline.return_value = mock_timeline_service
        mock_get_mig.return_value = mock_mig_service
        mock_get_linker.return_value = mock_entity_linker
        mock_get_cache.return_value = mock_cache_service

        # Execute entity linking task
        result = link_entities_for_matter.run("matter-123")

        # Verify entity linking succeeded
        assert result["status"] == "completed"
        assert result["events_with_links"] == 1

        # Verify job tracking for entity linking
        mock_job_tracker.create_job.assert_called_once()
        create_call = mock_job_tracker.create_job.call_args.kwargs
        assert create_call["matter_id"] == "matter-123"
        assert create_call["job_type"] == JobType.ENTITY_LINKING

        # Verify anomaly detection was triggered
        mock_detect_anomalies.delay.assert_called_once_with(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,  # Creates its own job
        )

        # Verify result includes anomaly trigger flag
        assert result["anomaly_detection_queued"] is True


class TestAnomalyDetectionJobCreatedOnAutoTrigger:
    """Tests that anomaly detection creates its own job when auto-triggered."""

    @pytest.fixture
    def mock_job_tracker(self) -> MagicMock:
        """Create mock job tracking service."""
        tracker = MagicMock()
        tracker.create_job = AsyncMock(
            return_value=MagicMock(id="anomaly-auto-job-456")
        )
        tracker.update_job_status = AsyncMock()
        return tracker

    @pytest.fixture
    def mock_anomaly_service(self) -> MagicMock:
        """Create mock anomaly service."""
        service = MagicMock()
        service.delete_anomalies_for_matter_sync.return_value = 0
        service.save_anomalies_sync.return_value = ["anomaly-1", "anomaly-2"]
        return service

    @pytest.fixture
    def mock_timeline_builder(self) -> MagicMock:
        """Create mock timeline builder with anomaly-producing events."""
        builder = MagicMock()

        # Create events that will trigger anomalies
        events = [
            create_mock_timeline_event(
                "e1", date(2024, 1, 15), EventType.HEARING, "Hearing before filing"
            ),
            create_mock_timeline_event(
                "e2", date(2024, 3, 20), EventType.FILING, "Application filed"
            ),
        ]

        mock_timeline = MagicMock()
        mock_timeline.events = events
        builder.build_timeline = AsyncMock(return_value=mock_timeline)
        return builder

    @pytest.fixture
    def mock_anomaly_detector(self) -> MagicMock:
        """Create mock anomaly detector that finds anomalies."""
        detector = MagicMock()

        # Mock detected anomalies
        mock_anomaly = MagicMock()
        mock_anomaly.id = None  # Not saved yet
        mock_anomaly.anomaly_type = AnomalyType.SEQUENCE_VIOLATION
        mock_anomaly.severity = "high"

        detector.detect_anomalies = AsyncMock(return_value=[mock_anomaly])
        return detector

    @pytest.fixture
    def mock_cache_service(self) -> MagicMock:
        """Create mock cache service."""
        service = MagicMock()
        service.invalidate_timeline = AsyncMock()
        return service

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_auto_triggered_anomaly_detection_creates_job(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_job_tracker: MagicMock,
        mock_anomaly_service: MagicMock,
        mock_timeline_builder: MagicMock,
        mock_anomaly_detector: MagicMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Auto-triggered detection should create and track its own job."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_job_tracker
        mock_get_anomaly_service.return_value = mock_anomaly_service
        mock_get_builder.return_value = mock_timeline_builder
        mock_get_detector.return_value = mock_anomaly_detector
        mock_get_cache.return_value = mock_cache_service

        # Execute anomaly detection without job_id (simulating auto-trigger)
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify job was created
        mock_job_tracker.create_job.assert_called_once()
        create_call = mock_job_tracker.create_job.call_args.kwargs
        assert create_call["matter_id"] == "matter-123"
        assert create_call["job_type"] == JobType.ANOMALY_DETECTION
        assert create_call["metadata"]["triggered_by"] == "pipeline"

        # Verify job status was updated throughout
        update_calls = mock_job_tracker.update_job_status.call_args_list
        assert len(update_calls) >= 2  # At least processing and completed

        # Verify result
        assert result["status"] == "completed"
        assert result["anomalies_detected"] == 1

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_anomalies_stored_in_database(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_job_tracker: MagicMock,
        mock_anomaly_service: MagicMock,
        mock_timeline_builder: MagicMock,
        mock_anomaly_detector: MagicMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Detected anomalies should be stored in database."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_job_tracker
        mock_get_anomaly_service.return_value = mock_anomaly_service
        mock_get_builder.return_value = mock_timeline_builder
        mock_get_detector.return_value = mock_anomaly_detector
        mock_get_cache.return_value = mock_cache_service

        # Execute anomaly detection
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify anomalies were saved
        mock_anomaly_service.save_anomalies_sync.assert_called_once()

        # Verify result contains saved anomaly IDs
        assert result["anomaly_ids"] == ["anomaly-1", "anomaly-2"]


class TestPipelineAnomalyTypes:
    """Tests for different anomaly types detected in pipeline."""

    @pytest.fixture
    def mock_job_tracker(self) -> MagicMock:
        """Create mock job tracking service."""
        tracker = MagicMock()
        tracker.create_job = AsyncMock(
            return_value=MagicMock(id="job-789")
        )
        tracker.update_job_status = AsyncMock()
        return tracker

    @pytest.fixture
    def mock_anomaly_service(self) -> MagicMock:
        """Create mock anomaly service."""
        service = MagicMock()
        service.delete_anomalies_for_matter_sync.return_value = 0
        service.save_anomalies_sync.return_value = []
        return service

    @pytest.fixture
    def mock_cache_service(self) -> MagicMock:
        """Create mock cache service."""
        service = MagicMock()
        service.invalidate_timeline = AsyncMock()
        return service

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_detects_sequence_violations(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_job_tracker: MagicMock,
        mock_anomaly_service: MagicMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Should detect sequence violations in timeline."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_job_tracker
        mock_get_anomaly_service.return_value = mock_anomaly_service
        mock_get_cache.return_value = mock_cache_service

        # Create events with sequence violation (hearing before filing)
        events = [
            create_mock_timeline_event(
                "e1", date(2024, 1, 15), EventType.HEARING, "Hearing"
            ),
            create_mock_timeline_event(
                "e2", date(2024, 3, 20), EventType.FILING, "Filing"
            ),
        ]
        mock_timeline = MagicMock()
        mock_timeline.events = events
        mock_get_builder.return_value.build_timeline = AsyncMock(return_value=mock_timeline)

        # Mock detector that finds sequence violation
        mock_anomaly = MagicMock()
        mock_anomaly.anomaly_type = AnomalyType.SEQUENCE_VIOLATION
        mock_get_detector.return_value.detect_anomalies = AsyncMock(
            return_value=[mock_anomaly]
        )

        # Execute
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify detection ran
        mock_get_detector.return_value.detect_anomalies.assert_called_once()
        assert result["anomalies_detected"] == 1

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_detects_timeline_gaps(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_job_tracker: MagicMock,
        mock_anomaly_service: MagicMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Should detect large gaps in timeline."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_job_tracker
        mock_get_anomaly_service.return_value = mock_anomaly_service
        mock_get_cache.return_value = mock_cache_service

        # Create events with large gap
        events = [
            create_mock_timeline_event(
                "e1", date(2024, 1, 15), EventType.FILING, "Filing"
            ),
            create_mock_timeline_event(
                "e2", date(2025, 6, 1), EventType.ORDER, "Order after 500+ days"
            ),
        ]
        mock_timeline = MagicMock()
        mock_timeline.events = events
        mock_get_builder.return_value.build_timeline = AsyncMock(return_value=mock_timeline)

        # Mock detector that finds gap
        mock_anomaly = MagicMock()
        mock_anomaly.anomaly_type = AnomalyType.GAP
        mock_anomaly.gap_days = 502
        mock_get_detector.return_value.detect_anomalies = AsyncMock(
            return_value=[mock_anomaly]
        )

        # Execute
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify gap anomaly detected
        assert result["anomalies_detected"] == 1


class TestPipelineIdempotency:
    """Tests for idempotency of pipeline operations."""

    @pytest.fixture
    def mock_job_tracker(self) -> MagicMock:
        """Create mock job tracking service."""
        tracker = MagicMock()
        tracker.create_job = AsyncMock(
            return_value=MagicMock(id="job-001")
        )
        tracker.update_job_status = AsyncMock()
        return tracker

    @pytest.fixture
    def mock_anomaly_service(self) -> MagicMock:
        """Create mock anomaly service."""
        service = MagicMock()
        service.delete_anomalies_for_matter_sync.return_value = 0
        service.save_anomalies_sync.return_value = []
        return service

    @pytest.fixture
    def mock_cache_service(self) -> MagicMock:
        """Create mock cache service."""
        service = MagicMock()
        service.invalidate_timeline = AsyncMock()
        return service

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_incremental_detection_does_not_delete_existing(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_job_tracker: MagicMock,
        mock_anomaly_service: MagicMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Incremental detection (force_redetect=False) should not delete existing."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_job_tracker
        mock_get_anomaly_service.return_value = mock_anomaly_service
        mock_get_cache.return_value = mock_cache_service

        mock_timeline = MagicMock()
        mock_timeline.events = []  # Empty timeline
        mock_get_builder.return_value.build_timeline = AsyncMock(return_value=mock_timeline)
        mock_get_detector.return_value.detect_anomalies = AsyncMock(return_value=[])

        # Execute with force_redetect=False (incremental, as used by auto-trigger)
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify delete was NOT called (force_redetect=False)
        mock_anomaly_service.delete_anomalies_for_matter_sync.assert_not_called()

        assert result["status"] == "completed"

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_force_redetect_deletes_existing(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_job_tracker: MagicMock,
        mock_anomaly_service: MagicMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Force redetect should delete existing anomalies first."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_job_tracker
        mock_get_anomaly_service.return_value = mock_anomaly_service
        mock_get_cache.return_value = mock_cache_service

        mock_timeline = MagicMock()
        mock_timeline.events = []
        mock_get_builder.return_value.build_timeline = AsyncMock(return_value=mock_timeline)
        mock_get_detector.return_value.detect_anomalies = AsyncMock(return_value=[])

        # Execute with force_redetect=True (manual trigger)
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=True,
            job_id=None,
        )

        # Verify delete WAS called
        mock_anomaly_service.delete_anomalies_for_matter_sync.assert_called_once_with(
            "matter-123"
        )

        assert result["status"] == "completed"
