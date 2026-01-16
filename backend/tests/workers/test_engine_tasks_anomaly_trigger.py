"""Tests for anomaly detection auto-trigger in engine tasks (Story 14-7).

Tests the automatic triggering of anomaly detection after entity linking
completes in the timeline pipeline.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLinkEntitiesForMatterAnomalyTrigger:
    """Tests for auto-trigger from link_entities_for_matter."""

    @pytest.fixture
    def mock_services(self) -> dict:
        """Create mock services for testing."""
        job_tracker = MagicMock()
        job_tracker.create_job = AsyncMock(
            return_value=MagicMock(id="job-123")
        )
        job_tracker.update_job_status = AsyncMock()

        timeline_service = MagicMock()
        timeline_service.get_events_for_entity_linking_sync.return_value = []

        mig_service = MagicMock()
        mig_service.get_entities_by_matter = AsyncMock(return_value=([], 0))

        entity_linker = MagicMock()

        cache_service = MagicMock()
        cache_service.invalidate_timeline = AsyncMock()

        return {
            "job_tracker": job_tracker,
            "timeline_service": timeline_service,
            "mig_service": mig_service,
            "entity_linker": entity_linker,
            "cache_service": cache_service,
        }

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_triggers_anomaly_detection_when_events_linked(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should trigger anomaly detection when events have been linked."""
        from app.workers.tasks.engine_tasks import link_entities_for_matter

        # Setup mocks
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Create mock events with entity links
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Test event"
        mock_event.document_id = "doc-1"
        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = [
            mock_event
        ]

        # Create mock entities
        mock_entity = MagicMock()
        mock_entity.id = "entity-1"
        mock_entity.canonical_name = "Test Entity"
        mock_services["mig_service"].get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )

        # Entity linker returns entity IDs
        mock_services["entity_linker"].link_entities_to_event_sync.return_value = [
            "entity-1"
        ]

        # Execute task
        result = link_entities_for_matter.run("matter-123")

        # Verify anomaly detection was triggered
        mock_detect_anomalies.delay.assert_called_once_with(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify result includes anomaly_detection_queued flag
        assert result["anomaly_detection_queued"] is True
        assert result["status"] == "completed"
        assert result["events_with_links"] == 1

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_triggers_with_events_but_no_links(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should trigger anomaly detection when events processed even if no links made."""
        from app.workers.tasks.engine_tasks import link_entities_for_matter

        # Setup mocks
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Create mock events
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Test event"
        mock_event.document_id = "doc-1"
        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = [
            mock_event
        ]

        # Create mock entities but no matches
        mock_entity = MagicMock()
        mock_entity.id = "entity-1"
        mock_services["mig_service"].get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )

        # Entity linker returns no matches
        mock_services["entity_linker"].link_entities_to_event_sync.return_value = []

        # Execute task
        result = link_entities_for_matter.run("matter-123")

        # Verify anomaly detection was still triggered (total_events > 0)
        mock_detect_anomalies.delay.assert_called_once_with(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        assert result["anomaly_detection_queued"] is True

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_does_not_trigger_when_no_events(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should not trigger anomaly detection when no events to process."""
        from app.workers.tasks.engine_tasks import link_entities_for_matter

        # Setup mocks - no events
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = []

        # Execute task
        result = link_entities_for_matter.run("matter-123")

        # Verify anomaly detection was NOT triggered
        mock_detect_anomalies.delay.assert_not_called()

        # Result should not have anomaly_detection_queued key
        assert "anomaly_detection_queued" not in result
        assert result["status"] == "completed"
        assert result["reason"] == "no_events_to_process"

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_uses_force_redetect_false(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should use force_redetect=False for incremental detection."""
        from app.workers.tasks.engine_tasks import link_entities_for_matter

        # Setup mocks
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Create mock event
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Test event"
        mock_event.document_id = "doc-1"
        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = [
            mock_event
        ]

        mock_entity = MagicMock()
        mock_services["mig_service"].get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )
        mock_services["entity_linker"].link_entities_to_event_sync.return_value = [
            "entity-1"
        ]

        # Execute task
        link_entities_for_matter.run("matter-123")

        # Verify force_redetect is False
        call_kwargs = mock_detect_anomalies.delay.call_args.kwargs
        assert call_kwargs["force_redetect"] is False


class TestLinkEntitiesAfterExtractionAnomalyTrigger:
    """Tests for auto-trigger from link_entities_after_extraction."""

    @pytest.fixture
    def mock_services(self) -> dict:
        """Create mock services for testing."""
        timeline_service = MagicMock()
        timeline_service.get_events_for_entity_linking_sync.return_value = []

        mig_service = MagicMock()
        mig_service.get_entities_by_matter = AsyncMock(return_value=([], 0))

        entity_linker = MagicMock()

        cache_service = MagicMock()
        cache_service.invalidate_timeline = AsyncMock()

        return {
            "timeline_service": timeline_service,
            "mig_service": mig_service,
            "entity_linker": entity_linker,
            "cache_service": cache_service,
        }

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    def test_triggers_anomaly_detection_when_events_linked(
        self,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should trigger anomaly detection after single document linking."""
        from app.workers.tasks.engine_tasks import link_entities_after_extraction

        # Setup mocks
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Create mock event for this document
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Test event"
        mock_event.document_id = "doc-123"
        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = [
            mock_event
        ]

        # Create mock entities
        mock_entity = MagicMock()
        mock_entity.id = "entity-1"
        mock_services["mig_service"].get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )

        # Entity linker returns entity IDs
        mock_services["entity_linker"].link_entities_to_event_sync.return_value = [
            "entity-1"
        ]

        # Execute task
        result = link_entities_after_extraction.run(
            document_id="doc-123",
            matter_id="matter-123",
        )

        # Verify anomaly detection was triggered
        mock_detect_anomalies.delay.assert_called_once_with(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify result
        assert result["anomaly_detection_queued"] is True
        assert result["status"] == "completed"
        assert result["events_linked"] == 1

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    def test_does_not_trigger_when_no_events_linked(
        self,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should not trigger when no events were linked."""
        from app.workers.tasks.engine_tasks import link_entities_after_extraction

        # Setup mocks
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Create mock event but no entity matches
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Test event"
        mock_event.document_id = "doc-123"
        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = [
            mock_event
        ]

        mock_entity = MagicMock()
        mock_services["mig_service"].get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )

        # Entity linker returns no matches
        mock_services["entity_linker"].link_entities_to_event_sync.return_value = []

        # Execute task
        result = link_entities_after_extraction.run(
            document_id="doc-123",
            matter_id="matter-123",
        )

        # Verify anomaly detection was NOT triggered
        mock_detect_anomalies.delay.assert_not_called()

        # Result should not have anomaly_detection_queued key
        assert "anomaly_detection_queued" not in result
        assert result["events_linked"] == 0


class TestDetectTimelineAnomaliesJobCreation:
    """Tests for job creation when detect_timeline_anomalies is auto-triggered."""

    @pytest.fixture
    def mock_services(self) -> dict:
        """Create mock services for testing."""
        job_tracker = MagicMock()
        job_tracker.create_job = AsyncMock(
            return_value=MagicMock(id="auto-job-123")
        )
        job_tracker.update_job_status = AsyncMock()

        anomaly_service = MagicMock()
        anomaly_service.delete_anomalies_for_matter_sync.return_value = 0
        anomaly_service.save_anomalies_sync.return_value = []

        timeline_builder = MagicMock()
        mock_timeline = MagicMock()
        mock_timeline.events = []
        timeline_builder.build_timeline = AsyncMock(return_value=mock_timeline)

        anomaly_detector = MagicMock()
        anomaly_detector.detect_anomalies = AsyncMock(return_value=[])

        cache_service = MagicMock()
        cache_service.invalidate_timeline = AsyncMock()

        return {
            "job_tracker": job_tracker,
            "anomaly_service": anomaly_service,
            "timeline_builder": timeline_builder,
            "anomaly_detector": anomaly_detector,
            "cache_service": cache_service,
        }

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_creates_job_when_job_id_is_none(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should create a job when job_id is None (auto-trigger case)."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_anomaly_service.return_value = mock_services["anomaly_service"]
        mock_get_builder.return_value = mock_services["timeline_builder"]
        mock_get_detector.return_value = mock_services["anomaly_detector"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Execute task without job_id (auto-trigger case)
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=False,
            job_id=None,
        )

        # Verify job was created
        mock_services["job_tracker"].create_job.assert_called_once()
        call_kwargs = mock_services["job_tracker"].create_job.call_args.kwargs
        assert call_kwargs["matter_id"] == "matter-123"
        assert call_kwargs["metadata"]["triggered_by"] == "pipeline"
        assert call_kwargs["metadata"]["force_redetect"] is False

        # Verify result
        assert result["status"] == "completed"

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_uses_provided_job_id_when_given(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should use provided job_id when given (manual trigger case)."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_anomaly_service.return_value = mock_services["anomaly_service"]
        mock_get_builder.return_value = mock_services["timeline_builder"]
        mock_get_detector.return_value = mock_services["anomaly_detector"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Execute task with job_id (manual trigger case)
        detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=False,
            job_id="existing-job-456",
        )

        # Verify job was NOT created
        mock_services["job_tracker"].create_job.assert_not_called()

        # Verify update_job_status was called with provided job_id
        update_calls = mock_services["job_tracker"].update_job_status.call_args_list
        assert len(update_calls) > 0
        # Check that first update used the provided job_id
        first_call_kwargs = update_calls[0].kwargs
        assert first_call_kwargs["job_id"] == "existing-job-456"


class TestAnomalyTriggerGracefulFailure:
    """Tests for graceful failure handling in anomaly trigger."""

    @pytest.fixture
    def mock_services(self) -> dict:
        """Create mock services for testing."""
        job_tracker = MagicMock()
        job_tracker.create_job = AsyncMock(
            return_value=MagicMock(id="job-123")
        )
        job_tracker.update_job_status = AsyncMock()

        timeline_service = MagicMock()

        mig_service = MagicMock()
        mig_service.get_entities_by_matter = AsyncMock(return_value=([], 0))

        entity_linker = MagicMock()

        cache_service = MagicMock()
        cache_service.invalidate_timeline = AsyncMock()

        return {
            "job_tracker": job_tracker,
            "timeline_service": timeline_service,
            "mig_service": mig_service,
            "entity_linker": entity_linker,
            "cache_service": cache_service,
        }

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_entity_linking_succeeds_even_if_anomaly_trigger_fails(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Entity linking should succeed even if anomaly trigger raises exception."""
        from app.workers.tasks.engine_tasks import link_entities_for_matter

        # Setup mocks
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Create mock event
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Test event"
        mock_event.document_id = "doc-1"
        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = [
            mock_event
        ]

        mock_entity = MagicMock()
        mock_services["mig_service"].get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )
        mock_services["entity_linker"].link_entities_to_event_sync.return_value = [
            "entity-1"
        ]

        # Make anomaly trigger fail
        mock_detect_anomalies.delay.side_effect = Exception("Celery broker unavailable")

        # Execute task - should NOT raise
        result = link_entities_for_matter.run("matter-123")

        # Verify entity linking succeeded
        assert result["status"] == "completed"
        assert result["events_with_links"] == 1

        # Verify anomaly_detection_queued is False due to failure
        assert result["anomaly_detection_queued"] is False

    @patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies")
    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_event_entity_linker")
    @patch("app.workers.tasks.engine_tasks.get_mig_graph_service")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    def test_document_linking_succeeds_even_if_anomaly_trigger_fails(
        self,
        mock_get_timeline: MagicMock,
        mock_get_mig: MagicMock,
        mock_get_linker: MagicMock,
        mock_get_cache: MagicMock,
        mock_detect_anomalies: MagicMock,
        mock_services: dict,
    ) -> None:
        """Document linking should succeed even if anomaly trigger fails."""
        from app.workers.tasks.engine_tasks import link_entities_after_extraction

        # Setup mocks
        mock_get_timeline.return_value = mock_services["timeline_service"]
        mock_get_mig.return_value = mock_services["mig_service"]
        mock_get_linker.return_value = mock_services["entity_linker"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Create mock event
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Test event"
        mock_event.document_id = "doc-123"
        mock_services["timeline_service"].get_events_for_entity_linking_sync.return_value = [
            mock_event
        ]

        mock_entity = MagicMock()
        mock_services["mig_service"].get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )
        mock_services["entity_linker"].link_entities_to_event_sync.return_value = [
            "entity-1"
        ]

        # Make anomaly trigger fail
        mock_detect_anomalies.delay.side_effect = Exception("Redis connection failed")

        # Execute task - should NOT raise
        result = link_entities_after_extraction.run(
            document_id="doc-123",
            matter_id="matter-123",
        )

        # Verify linking succeeded
        assert result["status"] == "completed"
        assert result["events_linked"] == 1

        # Verify anomaly_detection_queued is False due to failure
        assert result["anomaly_detection_queued"] is False


class TestManualRetriggerAfterAutoTriggerFailure:
    """Tests that manual re-trigger works after auto-trigger fails."""

    @pytest.fixture
    def mock_services(self) -> dict:
        """Create mock services for testing."""
        job_tracker = MagicMock()
        job_tracker.create_job = AsyncMock(
            return_value=MagicMock(id="manual-job-789")
        )
        job_tracker.update_job_status = AsyncMock()

        anomaly_service = MagicMock()
        anomaly_service.delete_anomalies_for_matter_sync.return_value = 0
        anomaly_service.save_anomalies_sync.return_value = ["anomaly-1"]

        timeline_builder = MagicMock()
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_timeline = MagicMock()
        mock_timeline.events = [mock_event]
        timeline_builder.build_timeline = AsyncMock(return_value=mock_timeline)

        anomaly_detector = MagicMock()
        mock_anomaly = MagicMock()
        mock_anomaly.id = "anomaly-1"
        anomaly_detector.detect_anomalies = AsyncMock(return_value=[mock_anomaly])

        cache_service = MagicMock()
        cache_service.invalidate_timeline = AsyncMock()

        return {
            "job_tracker": job_tracker,
            "anomaly_service": anomaly_service,
            "timeline_builder": timeline_builder,
            "anomaly_detector": anomaly_detector,
            "cache_service": cache_service,
        }

    @patch("app.workers.tasks.engine_tasks.get_timeline_cache_service")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_detector")
    @patch("app.workers.tasks.engine_tasks.get_timeline_builder")
    @patch("app.workers.tasks.engine_tasks.get_anomaly_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_manual_trigger_works_after_failed_auto_trigger(
        self,
        mock_get_job_tracker: MagicMock,
        mock_get_anomaly_service: MagicMock,
        mock_get_builder: MagicMock,
        mock_get_detector: MagicMock,
        mock_get_cache: MagicMock,
        mock_services: dict,
    ) -> None:
        """Manual API trigger should work even if previous auto-trigger failed."""
        from app.workers.tasks.engine_tasks import detect_timeline_anomalies

        # Setup mocks
        mock_get_job_tracker.return_value = mock_services["job_tracker"]
        mock_get_anomaly_service.return_value = mock_services["anomaly_service"]
        mock_get_builder.return_value = mock_services["timeline_builder"]
        mock_get_detector.return_value = mock_services["anomaly_detector"]
        mock_get_cache.return_value = mock_services["cache_service"]

        # Execute task (simulating manual trigger via API)
        result = detect_timeline_anomalies.run(
            matter_id="matter-123",
            force_redetect=True,
            job_id=None,  # API creates job, but task should also work
        )

        # Verify successful detection
        assert result["status"] == "completed"
        assert result["events_analyzed"] == 1
        assert result["anomalies_detected"] == 1
        assert result["anomaly_ids"] == ["anomaly-1"]
