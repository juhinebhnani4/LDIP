"""Timeline Engine for date extraction and event classification.

This module provides services for extracting dates from legal documents,
classifying events, and building timelines from case materials.

Story 4-1: Date Extraction with Gemini
Story 4-2: Event Classification
Story 4-3: Events Table + MIG Integration
Story 4-4: Timeline Anomaly Detection
"""

from app.engines.timeline.date_extractor import (
    DateExtractor,
    DateExtractorError,
    DateConfigurationError,
    get_date_extractor,
)
from app.engines.timeline.prompts import (
    DATE_EXTRACTION_SYSTEM_PROMPT,
    DATE_EXTRACTION_USER_PROMPT,
)

__all__ = [
    # Extractor
    "DateExtractor",
    "DateExtractorError",
    "DateConfigurationError",
    "get_date_extractor",
    # Prompts
    "DATE_EXTRACTION_SYSTEM_PROMPT",
    "DATE_EXTRACTION_USER_PROMPT",
]
