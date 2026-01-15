"""Legal workflow sequence rules for timeline anomaly detection.

Defines expected sequences for different case types and thresholds
for detecting anomalies in legal timelines.

Story 4-4: Timeline Anomaly Detection
"""

from dataclasses import dataclass
from enum import Enum

from app.models.timeline import EventType

# =============================================================================
# Case Type Enum
# =============================================================================


class CaseType(str, Enum):
    """Types of legal cases with defined workflow sequences."""

    SARFAESI = "sarfaesi"  # SARFAESI proceedings (most common)
    CIVIL_SUIT = "civil_suit"  # General civil suit
    ARBITRATION = "arbitration"  # Arbitration proceedings
    GENERAL = "general"  # Default/unknown case type


# =============================================================================
# Sequence Definitions
# =============================================================================


# Expected event type order for SARFAESI proceedings (Indian law)
# SARFAESI: Securitisation and Reconstruction of Financial Assets
# and Enforcement of Security Interest Act
SARFAESI_SEQUENCE: list[EventType] = [
    EventType.TRANSACTION,  # 1. Loan agreement, disbursement
    EventType.NOTICE,  # 2. 13(2) notice to borrower (60 days statutory)
    EventType.FILING,  # 3. Possession application under 13(4)
    EventType.HEARING,  # 4. DRT/DRAT hearing
    EventType.ORDER,  # 5. Tribunal order
]

# Expected event type order for general civil suits
CIVIL_SUIT_SEQUENCE: list[EventType] = [
    EventType.TRANSACTION,  # 1. Underlying transaction/event
    EventType.NOTICE,  # 2. Legal notice (optional but common)
    EventType.FILING,  # 3. Plaint/petition filing
    EventType.HEARING,  # 4. Court hearings
    EventType.ORDER,  # 5. Court order/judgment
]

# Expected event type order for arbitration proceedings
ARBITRATION_SEQUENCE: list[EventType] = [
    EventType.TRANSACTION,  # 1. Contract with arbitration clause
    EventType.NOTICE,  # 2. Notice invoking arbitration
    EventType.FILING,  # 3. Statement of claim
    EventType.HEARING,  # 4. Arbitration hearings
    EventType.ORDER,  # 5. Arbitral award
]

# Default sequence for unknown case types
GENERAL_SEQUENCE: list[EventType] = [
    EventType.TRANSACTION,
    EventType.NOTICE,
    EventType.FILING,
    EventType.HEARING,
    EventType.ORDER,
]

# Map case type to expected sequence
CASE_SEQUENCES: dict[CaseType, list[EventType]] = {
    CaseType.SARFAESI: SARFAESI_SEQUENCE,
    CaseType.CIVIL_SUIT: CIVIL_SUIT_SEQUENCE,
    CaseType.ARBITRATION: ARBITRATION_SEQUENCE,
    CaseType.GENERAL: GENERAL_SEQUENCE,
}


# =============================================================================
# Gap Thresholds
# =============================================================================


@dataclass
class GapThreshold:
    """Thresholds for detecting gap anomalies between event types."""

    warning_days: int  # Days before flagging as MEDIUM severity
    critical_days: int  # Days before flagging as HIGH severity
    description: str  # Human-readable description


# Gap thresholds for event type pairs
# Key: (from_event_type, to_event_type)
GAP_THRESHOLDS: dict[tuple[str, str], GapThreshold] = {
    # NOTICE → FILING: SARFAESI requires 60 days, but >180 is unusual
    ("notice", "filing"): GapThreshold(
        warning_days=180,
        critical_days=365,
        description="Time between notice and filing exceeds typical range",
    ),
    # FILING → HEARING: Courts should schedule hearings within reasonable time
    ("filing", "hearing"): GapThreshold(
        warning_days=90,
        critical_days=180,
        description="Significant delay between filing and first hearing",
    ),
    # HEARING → ORDER: Orders typically come within weeks of final hearing
    ("hearing", "order"): GapThreshold(
        warning_days=60,
        critical_days=120,
        description="Unusual delay between hearing and order",
    ),
    # TRANSACTION → NOTICE: Long gaps may indicate limitation issues
    ("transaction", "notice"): GapThreshold(
        warning_days=365,
        critical_days=730,  # 2 years
        description="Long gap between transaction and notice - check limitation",
    ),
    # NOTICE → HEARING (direct, if filing is skipped/missing)
    ("notice", "hearing"): GapThreshold(
        warning_days=180,
        critical_days=365,
        description="Long gap between notice and hearing - verify filing exists",
    ),
    # ORDER → FILING (appeals)
    ("order", "filing"): GapThreshold(
        warning_days=30,
        critical_days=45,
        description="Appeal filing deadline may be at risk",
    ),
}


# Default threshold for unspecified event type pairs
DEFAULT_GAP_THRESHOLD = GapThreshold(
    warning_days=180,
    critical_days=365,
    description="Unusual time gap between related events",
)


# =============================================================================
# Sequence Violation Severity Rules
# =============================================================================


# Critical violations: These event pairs being out of order are HIGH severity
CRITICAL_SEQUENCE_VIOLATIONS: set[tuple[str, str]] = {
    ("hearing", "filing"),  # Hearing before filing is serious
    ("order", "filing"),  # Order before filing is serious
    ("order", "hearing"),  # Order before hearing is unusual
}

# Medium violations: These are concerning but may have valid explanations
MEDIUM_SEQUENCE_VIOLATIONS: set[tuple[str, str]] = {
    ("filing", "notice"),  # Filing before notice - may be emergency
    ("hearing", "notice"),  # Hearing before notice
}


# =============================================================================
# Validator Class
# =============================================================================


@dataclass
class SequenceViolation:
    """Represents a detected sequence violation."""

    event_a_id: str
    event_a_type: str
    event_b_id: str
    event_b_type: str
    expected_position_a: int
    expected_position_b: int
    actual_position_a: int
    actual_position_b: int


class LegalSequenceValidator:
    """Validates event sequences against expected legal workflows.

    Example:
        >>> validator = LegalSequenceValidator()
        >>> sequence = validator.get_expected_sequence(CaseType.SARFAESI)
        >>> violations = validator.validate_sequence(events, CaseType.SARFAESI)
    """

    @staticmethod
    def get_expected_sequence(case_type: CaseType | str) -> list[EventType]:
        """Get expected event type sequence for a case type.

        Args:
            case_type: Case type enum or string.

        Returns:
            List of EventType in expected order.
        """
        if isinstance(case_type, str):
            try:
                case_type = CaseType(case_type.lower())
            except ValueError:
                case_type = CaseType.GENERAL

        return CASE_SEQUENCES.get(case_type, GENERAL_SEQUENCE)

    @staticmethod
    def get_event_position(
        event_type: EventType | str, sequence: list[EventType]
    ) -> int:
        """Get the position of an event type in the expected sequence.

        Args:
            event_type: Event type to find.
            sequence: Expected sequence.

        Returns:
            Position (0-indexed) or -1 if not in sequence.
        """
        if isinstance(event_type, str):
            try:
                event_type = EventType(event_type.lower())
            except ValueError:
                return -1

        try:
            return sequence.index(event_type)
        except ValueError:
            return -1

    @staticmethod
    def get_gap_threshold(
        from_type: EventType | str, to_type: EventType | str
    ) -> GapThreshold:
        """Get gap threshold for a pair of event types.

        Args:
            from_type: Earlier event type.
            to_type: Later event type.

        Returns:
            GapThreshold for the pair.
        """
        # Normalize to strings
        from_str = from_type.value if isinstance(from_type, EventType) else from_type
        to_str = to_type.value if isinstance(to_type, EventType) else to_type

        key = (from_str.lower(), to_str.lower())
        return GAP_THRESHOLDS.get(key, DEFAULT_GAP_THRESHOLD)

    @staticmethod
    def is_critical_violation(
        event_a_type: EventType | str, event_b_type: EventType | str
    ) -> bool:
        """Check if a sequence violation is critical severity.

        Args:
            event_a_type: First event type (that appeared first but shouldn't have).
            event_b_type: Second event type (that appeared second but should have been first).

        Returns:
            True if this is a critical violation.
        """
        a_str = event_a_type.value if isinstance(event_a_type, EventType) else event_a_type
        b_str = event_b_type.value if isinstance(event_b_type, EventType) else event_b_type

        return (a_str.lower(), b_str.lower()) in CRITICAL_SEQUENCE_VIOLATIONS

    @staticmethod
    def is_medium_violation(
        event_a_type: EventType | str, event_b_type: EventType | str
    ) -> bool:
        """Check if a sequence violation is medium severity.

        Args:
            event_a_type: First event type.
            event_b_type: Second event type.

        Returns:
            True if this is a medium severity violation.
        """
        a_str = event_a_type.value if isinstance(event_a_type, EventType) else event_a_type
        b_str = event_b_type.value if isinstance(event_b_type, EventType) else event_b_type

        return (a_str.lower(), b_str.lower()) in MEDIUM_SEQUENCE_VIOLATIONS


# =============================================================================
# Module-level convenience functions
# =============================================================================


def get_legal_sequence_validator() -> LegalSequenceValidator:
    """Get a LegalSequenceValidator instance.

    Returns:
        LegalSequenceValidator instance.
    """
    return LegalSequenceValidator()
