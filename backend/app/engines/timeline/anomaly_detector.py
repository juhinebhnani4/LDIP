"""Timeline Anomaly Detector for identifying unusual patterns in legal timelines.

Detects sequence violations, gaps, duplicates, and outliers in timeline
events to help attorneys identify potential issues.

Story 4-4: Timeline Anomaly Detection
"""

from datetime import date, timedelta

import structlog
from rapidfuzz import fuzz

from app.engines.timeline.legal_sequences import (
    CaseType,
    LegalSequenceValidator,
    get_legal_sequence_validator,
)
from app.engines.timeline.timeline_builder import TimelineEvent
from app.models.anomaly import (
    AnomalyCreate,
    AnomalySeverity,
    AnomalyType,
)
from app.models.timeline import EventType

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================


# Event types that can be part of a legal sequence
SEQUENCEABLE_TYPES: set[str] = {
    EventType.FILING.value,
    EventType.NOTICE.value,
    EventType.HEARING.value,
    EventType.ORDER.value,
    EventType.TRANSACTION.value,
}

# Text similarity threshold for duplicate detection (0-100)
DUPLICATE_SIMILARITY_THRESHOLD = 85

# Outlier thresholds
# Allow 2 years in future for scheduled hearings/deadlines
OUTLIER_YEARS_FUTURE = 2  # Future dates beyond this are outliers
OUTLIER_YEARS_PAST_WARNING = 10  # >10 years before earliest event
OUTLIER_YEARS_PAST_CRITICAL = 30  # >30 years before earliest event

# Event types that can legitimately have future dates
FUTURE_ALLOWED_EVENT_TYPES: set[str] = {
    EventType.HEARING.value,
    EventType.DEADLINE.value,
}


# =============================================================================
# Anomaly Detector Class
# =============================================================================


class TimelineAnomalyDetector:
    """Detects anomalies in timeline events.

    Implements rule-based detection for:
    - Sequence violations (events out of expected legal order)
    - Gap anomalies (unusual time gaps between related events)
    - Duplicates (potential duplicate events)
    - Outliers (statistically anomalous dates)

    Example:
        >>> detector = TimelineAnomalyDetector()
        >>> anomalies = await detector.detect_anomalies(matter_id, events)
    """

    def __init__(self) -> None:
        """Initialize the anomaly detector."""
        self._validator: LegalSequenceValidator | None = None

    @property
    def validator(self) -> LegalSequenceValidator:
        """Get the legal sequence validator."""
        if self._validator is None:
            self._validator = get_legal_sequence_validator()
        return self._validator

    async def detect_anomalies(
        self,
        matter_id: str,
        events: list[TimelineEvent],
        case_type: CaseType | str = CaseType.SARFAESI,
    ) -> list[AnomalyCreate]:
        """Detect all anomalies in a list of timeline events.

        Args:
            matter_id: Matter UUID.
            events: List of timeline events to analyze.
            case_type: Type of legal case (for sequence validation).

        Returns:
            List of detected anomalies.
        """
        if not events:
            logger.debug("anomaly_detection_empty_timeline", matter_id=matter_id)
            return []

        # Sort events by date for consistent analysis
        sorted_events = sorted(events, key=lambda e: e.event_date)

        all_anomalies: list[AnomalyCreate] = []

        # Run all detection algorithms
        sequence_violations = self.detect_sequence_violations(
            sorted_events, matter_id, case_type
        )
        all_anomalies.extend(sequence_violations)

        gap_anomalies = self.detect_gaps(sorted_events, matter_id)
        all_anomalies.extend(gap_anomalies)

        duplicates = self.detect_duplicates(sorted_events, matter_id)
        all_anomalies.extend(duplicates)

        outliers = self.detect_outliers(sorted_events, matter_id)
        all_anomalies.extend(outliers)

        logger.info(
            "anomaly_detection_complete",
            matter_id=matter_id,
            events_analyzed=len(events),
            anomalies_found=len(all_anomalies),
            sequence_violations=len(sequence_violations),
            gaps=len(gap_anomalies),
            duplicates=len(duplicates),
            outliers=len(outliers),
        )

        return all_anomalies

    def detect_sequence_violations(
        self,
        events: list[TimelineEvent],
        matter_id: str,
        case_type: CaseType | str = CaseType.SARFAESI,
    ) -> list[AnomalyCreate]:
        """Detect events that are out of expected legal workflow order.

        Algorithm:
        1. Filter to sequenceable event types
        2. Sort by date
        3. Compare each consecutive pair against expected sequence
        4. Flag violations where later event should have come earlier

        Args:
            events: Sorted list of timeline events.
            matter_id: Matter UUID.
            case_type: Type of legal case.

        Returns:
            List of sequence violation anomalies.
        """
        # Filter to sequenceable event types only
        seq_events = [
            e for e in events
            if e.event_type.value in SEQUENCEABLE_TYPES
        ]

        if len(seq_events) < 2:
            return []

        expected_sequence = self.validator.get_expected_sequence(case_type)
        anomalies: list[AnomalyCreate] = []

        # Check each consecutive pair
        for i in range(len(seq_events) - 1):
            event_a = seq_events[i]
            event_b = seq_events[i + 1]

            pos_a = self.validator.get_event_position(event_a.event_type, expected_sequence)
            pos_b = self.validator.get_event_position(event_b.event_type, expected_sequence)

            # Skip if either type is not in the expected sequence
            if pos_a == -1 or pos_b == -1:
                continue

            # Violation: event_b should have come before event_a
            if pos_b < pos_a:
                severity = self._calculate_sequence_severity(
                    event_a.event_type.value, event_b.event_type.value
                )

                # Generate explanation
                explanation = self._generate_sequence_explanation(
                    event_a, event_b, expected_sequence, pos_a, pos_b
                )

                anomalies.append(
                    AnomalyCreate(
                        matter_id=matter_id,
                        anomaly_type=AnomalyType.SEQUENCE_VIOLATION,
                        severity=severity,
                        title=f"{event_b.event_type.value.capitalize()} after {event_a.event_type.value}",
                        explanation=explanation,
                        event_ids=[event_a.event_id, event_b.event_id],
                        expected_order=[event_b.event_type.value, event_a.event_type.value],
                        actual_order=[event_a.event_type.value, event_b.event_type.value],
                        confidence=0.9,
                    )
                )

        return anomalies

    def detect_gaps(
        self,
        events: list[TimelineEvent],
        matter_id: str,
    ) -> list[AnomalyCreate]:
        """Detect unusual time gaps between consecutive events.

        Algorithm:
        1. Filter to sequenceable event types
        2. For each consecutive pair, calculate gap in days
        3. Compare against thresholds for that event type pair
        4. Flag gaps exceeding warning or critical thresholds

        Args:
            events: Sorted list of timeline events.
            matter_id: Matter UUID.

        Returns:
            List of gap anomalies.
        """
        # Filter to sequenceable event types
        seq_events = [
            e for e in events
            if e.event_type.value in SEQUENCEABLE_TYPES
        ]

        if len(seq_events) < 2:
            return []

        anomalies: list[AnomalyCreate] = []

        for i in range(len(seq_events) - 1):
            event_a = seq_events[i]
            event_b = seq_events[i + 1]

            # Calculate gap in days
            gap_days = (event_b.event_date - event_a.event_date).days

            # Get threshold for this event type pair
            threshold = self.validator.get_gap_threshold(
                event_a.event_type, event_b.event_type
            )

            # Skip if gap is within normal range
            if gap_days <= threshold.warning_days:
                continue

            # Determine severity
            if gap_days > threshold.critical_days:
                severity = AnomalySeverity.HIGH
            else:
                severity = AnomalySeverity.MEDIUM

            # Generate explanation
            explanation = (
                f"{gap_days} days between {event_a.event_type.value.capitalize()} "
                f"({event_a.event_date.isoformat()}) and "
                f"{event_b.event_type.value.capitalize()} ({event_b.event_date.isoformat()}). "
                f"{threshold.description}. "
                f"Possible causes: negotiation period, borrower response pending, "
                f"administrative delays, or strategic timing."
            )

            anomalies.append(
                AnomalyCreate(
                    matter_id=matter_id,
                    anomaly_type=AnomalyType.GAP,
                    severity=severity,
                    title=f"Unusual gap between {event_a.event_type.value} and {event_b.event_type.value}",
                    explanation=explanation,
                    event_ids=[event_a.event_id, event_b.event_id],
                    gap_days=gap_days,
                    confidence=0.95,
                )
            )

        return anomalies

    def detect_duplicates(
        self,
        events: list[TimelineEvent],
        matter_id: str,
    ) -> list[AnomalyCreate]:
        """Detect potential duplicate events.

        Algorithm:
        1. Group events by date
        2. Use token-set pre-filtering to reduce O(N²) comparisons
        3. Only run expensive fuzzy matching on likely candidates
        4. Flag pairs with high similarity as potential duplicates

        Args:
            events: List of timeline events.
            matter_id: Matter UUID.

        Returns:
            List of duplicate anomalies.
        """
        if len(events) < 2:
            return []

        # Group events by date
        events_by_date: dict[date, list[TimelineEvent]] = {}
        for event in events:
            if event.event_date not in events_by_date:
                events_by_date[event.event_date] = []
            events_by_date[event.event_date].append(event)

        anomalies: list[AnomalyCreate] = []
        seen_pairs: set[tuple[str, str]] = set()

        for event_date, date_events in events_by_date.items():
            if len(date_events) < 2:
                continue

            # Pre-compute token sets for O(N²) -> O(N) pre-filtering
            # This avoids expensive fuzzy matching on obviously different descriptions
            token_sets = []
            for event in date_events:
                # Create a set of significant words (3+ chars, lowercase)
                tokens = {
                    word.lower()
                    for word in event.description.split()
                    if len(word) >= 3
                }
                token_sets.append((event, tokens))

            # Compare pairs using token overlap as pre-filter
            for i in range(len(token_sets)):
                event_a, tokens_a = token_sets[i]

                for j in range(i + 1, len(token_sets)):
                    event_b, tokens_b = token_sets[j]

                    # Skip if already checked this pair
                    pair_key = tuple(sorted([event_a.event_id, event_b.event_id]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Pre-filter: require at least 30% token overlap before expensive comparison
                    # This dramatically reduces comparisons for large date buckets
                    if tokens_a and tokens_b:
                        overlap = len(tokens_a & tokens_b)
                        min_tokens = min(len(tokens_a), len(tokens_b))
                        if min_tokens > 0 and (overlap / min_tokens) < 0.3:
                            continue  # Skip expensive comparison

                    # Calculate description similarity (expensive operation)
                    similarity = fuzz.ratio(
                        event_a.description.lower(),
                        event_b.description.lower(),
                    )

                    if similarity >= DUPLICATE_SIMILARITY_THRESHOLD:
                        # Determine severity based on event types
                        severity = self._calculate_duplicate_severity(
                            event_a.event_type.value, event_b.event_type.value
                        )

                        explanation = (
                            f"Two events on {event_date.isoformat()} have {similarity}% similar descriptions. "
                            f"Event types: {event_a.event_type.value}, {event_b.event_type.value}. "
                            f"This may be: duplicate extraction from same source, "
                            f"same event mentioned in multiple documents, or genuinely separate events. "
                            f"Please review and merge if duplicate."
                        )

                        anomalies.append(
                            AnomalyCreate(
                                matter_id=matter_id,
                                anomaly_type=AnomalyType.DUPLICATE,
                                severity=severity,
                                title=f"Potential duplicate events on {event_date.isoformat()}",
                                explanation=explanation,
                                event_ids=[event_a.event_id, event_b.event_id],
                                confidence=similarity / 100.0,
                            )
                        )

        return anomalies

    def detect_outliers(
        self,
        events: list[TimelineEvent],
        matter_id: str,
    ) -> list[AnomalyCreate]:
        """Detect statistically anomalous dates.

        Algorithm:
        1. Calculate date range of timeline
        2. Flag dates far outside the typical range:
           - Future dates (always an error)
           - Very old dates (>10 years before earliest event)

        Args:
            events: List of timeline events.
            matter_id: Matter UUID.

        Returns:
            List of outlier anomalies.
        """
        if not events:
            return []

        today = date.today()
        anomalies: list[AnomalyCreate] = []

        # Find the typical date range (excluding extreme outliers)
        dates = [e.event_date for e in events]
        sorted_dates = sorted(dates)

        # Use median as reference if we have enough events
        if len(sorted_dates) >= 3:
            # Use middle 50% to establish baseline
            q1_idx = len(sorted_dates) // 4
            q3_idx = 3 * len(sorted_dates) // 4
            baseline_start = sorted_dates[q1_idx]
            baseline_end = sorted_dates[q3_idx]
        else:
            baseline_start = min(sorted_dates)
            baseline_end = max(sorted_dates)

        # Calculate future threshold date
        future_threshold = today + timedelta(days=int(OUTLIER_YEARS_FUTURE * 365.25))

        for event in events:
            # Check for future dates
            if event.event_date > today:
                days_in_future = (event.event_date - today).days
                years_in_future = days_in_future / 365.25

                # Allow scheduled hearings/deadlines within the threshold
                if (
                    event.event_type.value in FUTURE_ALLOWED_EVENT_TYPES
                    and event.event_date <= future_threshold
                ):
                    # This is a legitimate scheduled event, skip flagging
                    continue

                # Determine severity based on how far in the future
                if years_in_future > OUTLIER_YEARS_FUTURE:
                    severity = AnomalySeverity.HIGH
                    explanation = (
                        f"Event dated {event.event_date.isoformat()} is {days_in_future} days "
                        f"({years_in_future:.1f} years) in the future. This is likely a data entry error or OCR misread. "
                        f"Event type: {event.event_type.value}. Please verify the correct date."
                    )
                else:
                    # Future but within threshold - warn for non-hearing/deadline events
                    severity = AnomalySeverity.MEDIUM
                    explanation = (
                        f"Event dated {event.event_date.isoformat()} is {days_in_future} days "
                        f"in the future. Event type: {event.event_type.value}. "
                        f"If this is a scheduled hearing or deadline, this may be correct. Please verify."
                    )

                anomalies.append(
                    AnomalyCreate(
                        matter_id=matter_id,
                        anomaly_type=AnomalyType.OUTLIER,
                        severity=severity,
                        title=f"Future date: {event.event_date.isoformat()}",
                        explanation=explanation,
                        event_ids=[event.event_id],
                        confidence=0.95 if severity == AnomalySeverity.HIGH else 0.7,
                    )
                )
                continue

            # Check for very old dates
            years_before = (baseline_start - event.event_date).days / 365.25

            if years_before > OUTLIER_YEARS_PAST_CRITICAL:
                severity = AnomalySeverity.HIGH
                explanation = (
                    f"Event dated {event.event_date.isoformat()} is approximately {int(years_before)} years "
                    f"before the main timeline ({baseline_start.isoformat()} to {baseline_end.isoformat()}). "
                    f"This is likely an OCR error or incorrect date format. "
                    f"Possible causes: year misread (1990 vs 2019), century error, or date format confusion."
                )
            elif years_before > OUTLIER_YEARS_PAST_WARNING:
                severity = AnomalySeverity.MEDIUM
                explanation = (
                    f"Event dated {event.event_date.isoformat()} is approximately {int(years_before)} years "
                    f"before the main timeline. While this could be valid (e.g., original contract), "
                    f"please verify this date is correct."
                )
            else:
                continue

            anomalies.append(
                AnomalyCreate(
                    matter_id=matter_id,
                    anomaly_type=AnomalyType.OUTLIER,
                    severity=severity,
                    title=f"Unusually old date: {event.event_date.isoformat()}",
                    explanation=explanation,
                    event_ids=[event.event_id],
                    confidence=0.85,
                )
            )

        return anomalies

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_sequence_severity(
        self, event_a_type: str, event_b_type: str
    ) -> AnomalySeverity:
        """Calculate severity for a sequence violation.

        Args:
            event_a_type: Type of event that appeared first.
            event_b_type: Type of event that appeared second but should have been first.

        Returns:
            Severity level.
        """
        if self.validator.is_critical_violation(event_a_type, event_b_type):
            return AnomalySeverity.HIGH
        if self.validator.is_medium_violation(event_a_type, event_b_type):
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.MEDIUM  # Default to medium for other violations

    def _calculate_duplicate_severity(
        self, event_a_type: str, event_b_type: str
    ) -> AnomalySeverity:
        """Calculate severity for duplicate detection.

        Args:
            event_a_type: Type of first event.
            event_b_type: Type of second event.

        Returns:
            Severity level.
        """
        # Critical event types warrant higher severity
        critical_types = {"filing", "order"}
        if event_a_type in critical_types or event_b_type in critical_types:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def _generate_sequence_explanation(
        self,
        event_a: TimelineEvent,
        event_b: TimelineEvent,
        expected_sequence: list[EventType],
        pos_a: int,
        pos_b: int,
    ) -> str:
        """Generate detailed explanation for sequence violation.

        Args:
            event_a: First event (appeared first chronologically).
            event_b: Second event (should have appeared first per legal workflow).
            expected_sequence: Expected event type order.
            pos_a: Position of event_a type in sequence.
            pos_b: Position of event_b type in sequence.

        Returns:
            Detailed explanation string.
        """
        return (
            f"{event_b.event_type.value.capitalize()} dated {event_b.event_date.isoformat()} "
            f"appears after {event_a.event_type.value.capitalize()} dated {event_a.event_date.isoformat()}, "
            f"but typically {event_b.event_type.value} should precede {event_a.event_type.value} "
            f"in standard legal proceedings. "
            f"Possible causes: date entry error, exceptional legal procedure, parallel proceedings, "
            f"or document dated vs filed distinction."
        )


# =============================================================================
# Module-level factory function
# =============================================================================


def get_anomaly_detector() -> TimelineAnomalyDetector:
    """Get an anomaly detector instance.

    Note: Not cached as each request may need fresh analysis.

    Returns:
        TimelineAnomalyDetector instance.
    """
    return TimelineAnomalyDetector()
