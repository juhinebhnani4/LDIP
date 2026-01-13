"""Tests for Timeline Anomaly Detector.

Story 4-4: Timeline Anomaly Detection
"""

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.engines.timeline.anomaly_detector import (
    DUPLICATE_SIMILARITY_THRESHOLD,
    TimelineAnomalyDetector,
    get_anomaly_detector,
)
from app.engines.timeline.legal_sequences import (
    CaseType,
    LegalSequenceValidator,
    get_legal_sequence_validator,
)
from app.engines.timeline.timeline_builder import TimelineEvent
from app.models.anomaly import AnomalyCreate, AnomalySeverity, AnomalyType
from app.models.timeline import EventType


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def detector() -> TimelineAnomalyDetector:
    """Create a fresh TimelineAnomalyDetector instance."""
    return TimelineAnomalyDetector()


@pytest.fixture
def validator() -> LegalSequenceValidator:
    """Create a fresh LegalSequenceValidator instance."""
    return LegalSequenceValidator()


def create_event(
    event_id: str,
    event_date: date,
    event_type: EventType,
    description: str = "Test event",
) -> TimelineEvent:
    """Helper to create TimelineEvent objects for testing."""
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
# Tests for LegalSequenceValidator
# =============================================================================


class TestLegalSequenceValidator:
    """Tests for legal workflow sequence validation."""

    def test_get_expected_sequence_sarfaesi(self, validator: LegalSequenceValidator) -> None:
        """Should return SARFAESI sequence for that case type."""
        sequence = validator.get_expected_sequence(CaseType.SARFAESI)

        assert len(sequence) == 5
        assert sequence[0] == EventType.TRANSACTION
        assert sequence[1] == EventType.NOTICE
        assert sequence[2] == EventType.FILING
        assert sequence[3] == EventType.HEARING
        assert sequence[4] == EventType.ORDER

    def test_get_expected_sequence_general(self, validator: LegalSequenceValidator) -> None:
        """Should return general sequence for unknown case type."""
        sequence = validator.get_expected_sequence("unknown_type")

        assert len(sequence) == 5
        assert EventType.FILING in sequence

    def test_get_event_position(self, validator: LegalSequenceValidator) -> None:
        """Should return correct position in sequence."""
        sequence = validator.get_expected_sequence(CaseType.SARFAESI)

        pos_filing = validator.get_event_position(EventType.FILING, sequence)
        pos_notice = validator.get_event_position(EventType.NOTICE, sequence)

        assert pos_filing == 2
        assert pos_notice == 1
        assert pos_filing > pos_notice  # Filing comes after notice

    def test_get_event_position_not_in_sequence(self, validator: LegalSequenceValidator) -> None:
        """Should return -1 for event types not in sequence."""
        sequence = validator.get_expected_sequence(CaseType.SARFAESI)

        # DOCUMENT type is not in main sequence
        pos = validator.get_event_position(EventType.DOCUMENT, sequence)
        assert pos == -1

    def test_get_gap_threshold(self, validator: LegalSequenceValidator) -> None:
        """Should return correct thresholds for event pairs."""
        threshold = validator.get_gap_threshold(EventType.NOTICE, EventType.FILING)

        assert threshold.warning_days == 180
        assert threshold.critical_days == 365

    def test_get_gap_threshold_default(self, validator: LegalSequenceValidator) -> None:
        """Should return default threshold for unknown pairs."""
        threshold = validator.get_gap_threshold(EventType.DOCUMENT, EventType.DEADLINE)

        assert threshold.warning_days == 180  # Default
        assert threshold.critical_days == 365  # Default

    def test_is_critical_violation(self, validator: LegalSequenceValidator) -> None:
        """Should identify critical sequence violations."""
        # Hearing before filing is critical
        assert validator.is_critical_violation("hearing", "filing") is True
        # Order before filing is critical
        assert validator.is_critical_violation("order", "filing") is True
        # Notice before filing is not critical
        assert validator.is_critical_violation("notice", "filing") is False


# =============================================================================
# Tests for TimelineAnomalyDetector Initialization
# =============================================================================


class TestAnomalyDetectorInit:
    """Tests for TimelineAnomalyDetector initialization."""

    def test_init_creates_instance(self) -> None:
        """Should create TimelineAnomalyDetector instance."""
        detector = TimelineAnomalyDetector()
        assert detector is not None

    def test_factory_creates_new_instance(self) -> None:
        """Factory should create new instance each call."""
        detector1 = get_anomaly_detector()
        detector2 = get_anomaly_detector()

        # Different instances (not cached)
        assert detector1 is not detector2


# =============================================================================
# Tests for Sequence Violation Detection
# =============================================================================


class TestSequenceViolationDetection:
    """Tests for detecting sequence violations in timelines."""

    @pytest.mark.asyncio
    async def test_detect_hearing_before_filing(self, detector: TimelineAnomalyDetector) -> None:
        """Should detect hearing event occurring before filing."""
        events = [
            create_event("e1", date(2024, 1, 15), EventType.HEARING, "Hearing held"),
            create_event("e2", date(2024, 3, 20), EventType.FILING, "Filed application"),
        ]

        anomalies = detector.detect_sequence_violations(
            events, "matter-123", CaseType.SARFAESI
        )

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.SEQUENCE_VIOLATION
        assert "hearing" in anomalies[0].actual_order
        assert "filing" in anomalies[0].actual_order

    @pytest.mark.asyncio
    async def test_detect_order_before_hearing(self, detector: TimelineAnomalyDetector) -> None:
        """Should detect order event occurring before hearing."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.NOTICE, "Notice sent"),
            create_event("e2", date(2024, 2, 15), EventType.ORDER, "Order passed"),
            create_event("e3", date(2024, 3, 20), EventType.HEARING, "Hearing held"),
        ]

        anomalies = detector.detect_sequence_violations(
            events, "matter-123", CaseType.SARFAESI
        )

        assert len(anomalies) >= 1
        violation_types = [a.anomaly_type for a in anomalies]
        assert AnomalyType.SEQUENCE_VIOLATION in violation_types

    @pytest.mark.asyncio
    async def test_no_violation_correct_sequence(self, detector: TimelineAnomalyDetector) -> None:
        """Should not flag violations for correct sequence."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.NOTICE, "Notice sent"),
            create_event("e2", date(2024, 2, 15), EventType.FILING, "Filed"),
            create_event("e3", date(2024, 3, 20), EventType.HEARING, "Hearing"),
            create_event("e4", date(2024, 4, 25), EventType.ORDER, "Order"),
        ]

        anomalies = detector.detect_sequence_violations(
            events, "matter-123", CaseType.SARFAESI
        )

        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_skip_non_sequenceable_types(self, detector: TimelineAnomalyDetector) -> None:
        """Should skip event types not in legal sequence."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.DOCUMENT, "Document created"),
            create_event("e2", date(2024, 2, 15), EventType.DEADLINE, "Deadline"),
        ]

        anomalies = detector.detect_sequence_violations(
            events, "matter-123", CaseType.SARFAESI
        )

        # Should not flag violations for non-sequenceable types
        assert len(anomalies) == 0


# =============================================================================
# Tests for Gap Detection
# =============================================================================


class TestGapDetection:
    """Tests for detecting unusual time gaps."""

    @pytest.mark.asyncio
    async def test_detect_large_gap_notice_to_filing(self, detector: TimelineAnomalyDetector) -> None:
        """Should detect large gap between notice and filing."""
        events = [
            create_event("e1", date(2023, 1, 10), EventType.NOTICE, "Notice"),
            create_event("e2", date(2024, 3, 20), EventType.FILING, "Filing"),  # ~15 months gap
        ]

        anomalies = detector.detect_gaps(events, "matter-123")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.GAP
        assert anomalies[0].gap_days is not None
        assert anomalies[0].gap_days > 400  # More than a year

    @pytest.mark.asyncio
    async def test_gap_severity_warning_vs_critical(self, detector: TimelineAnomalyDetector) -> None:
        """Should assign correct severity based on gap length."""
        # Warning level gap (200 days)
        events_warning = [
            create_event("e1", date(2024, 1, 10), EventType.NOTICE, "Notice"),
            create_event("e2", date(2024, 7, 28), EventType.FILING, "Filing"),  # ~200 days
        ]

        # Critical level gap (400 days)
        events_critical = [
            create_event("e1", date(2023, 1, 10), EventType.NOTICE, "Notice"),
            create_event("e2", date(2024, 2, 14), EventType.FILING, "Filing"),  # ~400 days
        ]

        warning_anomalies = detector.detect_gaps(events_warning, "matter-123")
        critical_anomalies = detector.detect_gaps(events_critical, "matter-123")

        if warning_anomalies:
            assert warning_anomalies[0].severity == AnomalySeverity.MEDIUM

        if critical_anomalies:
            assert critical_anomalies[0].severity == AnomalySeverity.HIGH

    @pytest.mark.asyncio
    async def test_no_gap_normal_timing(self, detector: TimelineAnomalyDetector) -> None:
        """Should not flag gaps within normal range."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.NOTICE, "Notice"),
            create_event("e2", date(2024, 3, 15), EventType.FILING, "Filing"),  # ~65 days
        ]

        anomalies = detector.detect_gaps(events, "matter-123")

        assert len(anomalies) == 0


# =============================================================================
# Tests for Duplicate Detection
# =============================================================================


class TestDuplicateDetection:
    """Tests for detecting potential duplicate events."""

    @pytest.mark.asyncio
    async def test_detect_duplicates_same_date_similar_desc(self, detector: TimelineAnomalyDetector) -> None:
        """Should detect duplicates with same date and similar descriptions."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.FILING, "Application filed in DRT Mumbai"),
            create_event("e2", date(2024, 1, 10), EventType.FILING, "Application filed in DRT Mumbai court"),
        ]

        anomalies = detector.detect_duplicates(events, "matter-123")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.DUPLICATE
        assert len(anomalies[0].event_ids) == 2

    @pytest.mark.asyncio
    async def test_no_duplicate_different_dates(self, detector: TimelineAnomalyDetector) -> None:
        """Should not flag as duplicate if dates differ."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.FILING, "Application filed"),
            create_event("e2", date(2024, 1, 15), EventType.FILING, "Application filed"),
        ]

        anomalies = detector.detect_duplicates(events, "matter-123")

        assert len(anomalies) == 0  # Different dates, not duplicates

    @pytest.mark.asyncio
    async def test_no_duplicate_different_descriptions(self, detector: TimelineAnomalyDetector) -> None:
        """Should not flag as duplicate if descriptions very different."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.FILING, "Application filed in Mumbai"),
            create_event("e2", date(2024, 1, 10), EventType.HEARING, "Hearing held in Delhi"),
        ]

        anomalies = detector.detect_duplicates(events, "matter-123")

        # Very different descriptions should not be flagged
        assert len(anomalies) == 0


# =============================================================================
# Tests for Outlier Detection
# =============================================================================


class TestOutlierDetection:
    """Tests for detecting statistically anomalous dates."""

    @pytest.mark.asyncio
    async def test_detect_future_date(self, detector: TimelineAnomalyDetector) -> None:
        """Should detect dates in the future."""
        events = [
            create_event("e1", date(2024, 1, 10), EventType.NOTICE, "Notice"),
            create_event("e2", date(2099, 6, 15), EventType.FILING, "Future filing"),
        ]

        anomalies = detector.detect_outliers(events, "matter-123")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.OUTLIER
        assert anomalies[0].severity == AnomalySeverity.HIGH
        assert "future" in anomalies[0].title.lower()

    @pytest.mark.asyncio
    async def test_detect_very_old_date(self, detector: TimelineAnomalyDetector) -> None:
        """Should detect dates far in the past."""
        # Need enough events so that the baseline excludes the outlier
        events = [
            create_event("e1", date(1950, 1, 10), EventType.TRANSACTION, "Very old"),
            create_event("e2", date(2023, 6, 1), EventType.TRANSACTION, "Transaction"),
            create_event("e3", date(2024, 1, 10), EventType.NOTICE, "Notice"),
            create_event("e4", date(2024, 2, 15), EventType.FILING, "Filing"),
            create_event("e5", date(2024, 3, 20), EventType.HEARING, "Hearing"),
        ]

        anomalies = detector.detect_outliers(events, "matter-123")

        # Should detect the 1950 date as outlier
        outlier_anomalies = [
            a for a in anomalies
            if "1950" in a.title or "old" in a.title.lower()
        ]
        assert len(outlier_anomalies) >= 1

    @pytest.mark.asyncio
    async def test_no_outlier_normal_dates(self, detector: TimelineAnomalyDetector) -> None:
        """Should not flag normal date ranges as outliers."""
        events = [
            create_event("e1", date(2023, 6, 10), EventType.TRANSACTION, "Transaction"),
            create_event("e2", date(2024, 1, 10), EventType.NOTICE, "Notice"),
            create_event("e3", date(2024, 3, 15), EventType.FILING, "Filing"),
        ]

        anomalies = detector.detect_outliers(events, "matter-123")

        assert len(anomalies) == 0


# =============================================================================
# Tests for Full Anomaly Detection Pipeline
# =============================================================================


class TestFullAnomalyDetection:
    """Tests for the complete anomaly detection pipeline."""

    @pytest.mark.asyncio
    async def test_detect_multiple_anomaly_types(self, detector: TimelineAnomalyDetector) -> None:
        """Should detect multiple types of anomalies in one pass."""
        events = [
            # Sequence violation (hearing before filing)
            create_event("e1", date(2024, 1, 15), EventType.HEARING, "Hearing"),
            create_event("e2", date(2024, 3, 20), EventType.FILING, "Filing"),
            # Gap (large gap between filing and order)
            create_event("e3", date(2026, 1, 1), EventType.ORDER, "Order"),  # 2 year gap
        ]

        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        anomaly_types = {a.anomaly_type for a in anomalies}
        assert AnomalyType.SEQUENCE_VIOLATION in anomaly_types
        assert AnomalyType.GAP in anomaly_types

    @pytest.mark.asyncio
    async def test_empty_timeline_no_errors(self, detector: TimelineAnomalyDetector) -> None:
        """Should handle empty event list gracefully."""
        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=[],
            case_type=CaseType.SARFAESI,
        )

        assert anomalies == []

    @pytest.mark.asyncio
    async def test_single_event_no_errors(self, detector: TimelineAnomalyDetector) -> None:
        """Should handle single event gracefully."""
        events = [
            create_event("e1", date(2024, 1, 15), EventType.NOTICE, "Notice"),
        ]

        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        # Single event can't have sequence/gap violations
        seq_violations = [a for a in anomalies if a.anomaly_type == AnomalyType.SEQUENCE_VIOLATION]
        gap_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.GAP]

        assert len(seq_violations) == 0
        assert len(gap_anomalies) == 0

    @pytest.mark.asyncio
    async def test_all_events_same_date(self, detector: TimelineAnomalyDetector) -> None:
        """Should handle all events on same date."""
        same_date = date(2024, 1, 15)
        events = [
            create_event("e1", same_date, EventType.NOTICE, "Notice sent"),
            create_event("e2", same_date, EventType.FILING, "Application filed"),
            create_event("e3", same_date, EventType.HEARING, "Hearing held"),
        ]

        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        # Should not have gap anomalies (0 days between)
        gap_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.GAP]
        assert len(gap_anomalies) == 0

    @pytest.mark.asyncio
    async def test_anomaly_confidence_scores(self, detector: TimelineAnomalyDetector) -> None:
        """Should include confidence scores in anomalies."""
        events = [
            create_event("e1", date(2024, 1, 15), EventType.HEARING, "Hearing"),
            create_event("e2", date(2024, 3, 20), EventType.FILING, "Filing"),
        ]

        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        for anomaly in anomalies:
            assert 0.0 <= anomaly.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_anomaly_event_ids_populated(self, detector: TimelineAnomalyDetector) -> None:
        """Should include event IDs in anomalies."""
        events = [
            create_event("event-abc-123", date(2024, 1, 15), EventType.HEARING, "Hearing"),
            create_event("event-xyz-456", date(2024, 3, 20), EventType.FILING, "Filing"),
        ]

        anomalies = await detector.detect_anomalies(
            matter_id="matter-123",
            events=events,
            case_type=CaseType.SARFAESI,
        )

        for anomaly in anomalies:
            assert len(anomaly.event_ids) > 0
            # Event IDs should be from our test events
            for event_id in anomaly.event_ids:
                assert event_id in ["event-abc-123", "event-xyz-456"]
