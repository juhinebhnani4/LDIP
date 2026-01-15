"""Timeline Engine for date extraction and event classification.

This module provides services for extracting dates from legal documents,
classifying events, and building timelines from case materials.

Story 4-1: Date Extraction with Gemini
Story 4-2: Event Classification
Story 4-3: Events Table + MIG Integration
Story 4-4: Timeline Anomaly Detection
"""

from app.engines.timeline.anomaly_detector import (
    TimelineAnomalyDetector,
    get_anomaly_detector,
)
from app.engines.timeline.classification_prompts import (
    EVENT_CLASSIFICATION_BATCH_PROMPT,
    EVENT_CLASSIFICATION_SYSTEM_PROMPT,
    EVENT_CLASSIFICATION_USER_PROMPT,
)
from app.engines.timeline.date_extractor import (
    DateConfigurationError,
    DateExtractor,
    DateExtractorError,
    get_date_extractor,
)
from app.engines.timeline.entity_linker import (
    EntityLinkerError,
    EventEntityLinker,
    LinkerConfigurationError,
    get_event_entity_linker,
)
from app.engines.timeline.event_classifier import (
    ClassifierConfigurationError,
    EventClassifier,
    EventClassifierError,
    get_event_classifier,
)
from app.engines.timeline.legal_sequences import (
    CaseType,
    LegalSequenceValidator,
    get_legal_sequence_validator,
)
from app.engines.timeline.prompts import (
    DATE_EXTRACTION_SYSTEM_PROMPT,
    DATE_EXTRACTION_USER_PROMPT,
)
from app.engines.timeline.timeline_builder import (
    ConstructedTimeline,
    EntityTimelineView,
    TimelineBuilder,
    TimelineEvent,
    TimelineStatistics,
    get_timeline_builder,
)

__all__ = [
    # Date Extractor
    "DateExtractor",
    "DateExtractorError",
    "DateConfigurationError",
    "get_date_extractor",
    # Event Classifier (Story 4-2)
    "EventClassifier",
    "EventClassifierError",
    "ClassifierConfigurationError",
    "get_event_classifier",
    # Entity Linker (Story 4-3)
    "EventEntityLinker",
    "EntityLinkerError",
    "LinkerConfigurationError",
    "get_event_entity_linker",
    # Timeline Builder (Story 4-3)
    "TimelineBuilder",
    "ConstructedTimeline",
    "TimelineEvent",
    "TimelineStatistics",
    "EntityTimelineView",
    "get_timeline_builder",
    # Date Extraction Prompts
    "DATE_EXTRACTION_SYSTEM_PROMPT",
    "DATE_EXTRACTION_USER_PROMPT",
    # Classification Prompts (Story 4-2)
    "EVENT_CLASSIFICATION_SYSTEM_PROMPT",
    "EVENT_CLASSIFICATION_USER_PROMPT",
    "EVENT_CLASSIFICATION_BATCH_PROMPT",
    # Anomaly Detection (Story 4-4)
    "TimelineAnomalyDetector",
    "get_anomaly_detector",
    "CaseType",
    "LegalSequenceValidator",
    "get_legal_sequence_validator",
]
