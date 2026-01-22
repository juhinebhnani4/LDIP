"""Multi-intent classification models.

Story 6-1 Enhancement: Multi-Intent Classification Redesign

Provides data models for:
1. IntentSignal - Individual intent signals with confidence and provenance
2. CompoundIntent - Semantic relationships between multiple intents
3. MultiIntentClassification - Complete multi-intent classification result

CRITICAL: These models enable additive intent detection (vs winner-takes-all).
"""

from dataclasses import dataclass, field
from enum import Enum

from app.models.orchestrator import EngineType


class IntentSource(str, Enum):
    """Source of intent signal.

    Used to track provenance of each detected intent.

    Values:
        PATTERN: Fast-path regex match
        LLM: LLM classification refinement
        FALLBACK: Low-confidence safety net (RAG default)
        COMPOUND: Detected intent relationship
        COMPREHENSIVE: User requested comprehensive analysis
    """

    PATTERN = "pattern"
    LLM = "llm"
    FALLBACK = "fallback"
    COMPOUND = "compound"
    COMPREHENSIVE = "comprehensive"


@dataclass
class IntentSignal:
    """Individual intent signal with confidence and provenance.

    Represents a single detected intent from pattern matching or LLM.
    Multiple signals can be active simultaneously.

    Attributes:
        engine: Target engine for this intent
        confidence: Confidence score (0.0-1.0)
        source: How the signal was detected
        pattern_matched: Which regex pattern matched (for debugging)

    Example:
        >>> signal = IntentSignal(
        ...     engine=EngineType.CITATION,
        ...     confidence=0.9,
        ...     source=IntentSource.PATTERN,
        ...     pattern_matched=r"\\bcitations?\\b",
        ... )
    """

    engine: EngineType
    confidence: float
    source: IntentSource
    pattern_matched: str | None = None

    def __hash__(self) -> int:
        """Hash for deduplication."""
        return hash((self.engine, self.source))

    def __eq__(self, other: object) -> bool:
        """Equality based on engine and source."""
        if not isinstance(other, IntentSignal):
            return False
        return self.engine == other.engine and self.source == other.source


@dataclass
class CompoundIntent:
    """When multiple intents form a semantic relationship.

    Compound intents represent queries where multiple engines should
    work together with a specific aggregation strategy.

    Attributes:
        name: Human-readable name (e.g., "temporal_contradictions")
        primary_engine: Lead engine for response structure
        supporting_engines: Engines that supplement the primary
        aggregation_strategy: How to combine results

    Example:
        >>> compound = CompoundIntent(
        ...     name="temporal_contradictions",
        ...     primary_engine=EngineType.CONTRADICTION,
        ...     supporting_engines=[EngineType.TIMELINE],
        ...     aggregation_strategy="weave",
        ... )
    """

    name: str
    primary_engine: EngineType
    supporting_engines: list[EngineType]
    aggregation_strategy: str  # "weave" | "sequential" | "parallel_merge"


# Configuration thresholds
INCLUSION_THRESHOLD: float = 0.5  # Minimum confidence to include engine
HIGH_CONFIDENCE_THRESHOLD: float = 0.85  # Threshold for "certain" classification


@dataclass
class MultiIntentClassification:
    """Complete multi-intent classification result.

    Replaces the old single-intent IntentClassification for queries
    that require multiple engines.

    Attributes:
        signals: All detected intent signals
        compound_intent: Detected compound intent (if any)
        reasoning: Human-readable explanation
        llm_was_used: Whether LLM refinement was invoked

    Example:
        >>> classification = MultiIntentClassification(
        ...     signals=[
        ...         IntentSignal(EngineType.CITATION, 0.9, IntentSource.PATTERN),
        ...         IntentSignal(EngineType.CONTRADICTION, 0.85, IntentSource.PATTERN),
        ...     ],
        ...     compound_intent=None,
        ...     reasoning="Detected citation and contradiction keywords",
        ...     llm_was_used=False,
        ... )
        >>> classification.is_multi_intent
        True
        >>> classification.required_engines
        {EngineType.CITATION, EngineType.CONTRADICTION}
    """

    signals: list[IntentSignal] = field(default_factory=list)
    compound_intent: CompoundIntent | None = None
    reasoning: str = ""
    llm_was_used: bool = False

    @property
    def is_multi_intent(self) -> bool:
        """True if multiple engines should run."""
        return len(self.required_engines) > 1

    @property
    def required_engines(self) -> set[EngineType]:
        """All engines meeting inclusion threshold."""
        return {
            s.engine
            for s in self.signals
            if s.confidence >= INCLUSION_THRESHOLD
        }

    @property
    def primary_engine(self) -> EngineType:
        """Highest confidence engine (for response ordering).

        If a compound intent is detected, uses its primary_engine.
        Otherwise, returns the engine with highest confidence.
        Falls back to RAG if no signals present.
        """
        if self.compound_intent:
            return self.compound_intent.primary_engine
        if not self.signals:
            return EngineType.RAG
        return max(self.signals, key=lambda s: s.confidence).engine

    @property
    def aggregation_strategy(self) -> str:
        """How to combine results.

        Returns:
            - "single": One engine only
            - "parallel_merge": Section-based combination
            - "weave": Narrative integration
            - "sequential": Time-ordered structure
        """
        if self.compound_intent:
            return self.compound_intent.aggregation_strategy
        return "parallel_merge" if self.is_multi_intent else "single"

    @property
    def max_confidence(self) -> float:
        """Highest confidence among all signals."""
        if not self.signals:
            return 0.0
        return max(s.confidence for s in self.signals)

    def get_signals_for_engine(self, engine: EngineType) -> list[IntentSignal]:
        """Get all signals for a specific engine."""
        return [s for s in self.signals if s.engine == engine]

    def has_engine(self, engine: EngineType) -> bool:
        """Check if engine is in required engines."""
        return engine in self.required_engines
