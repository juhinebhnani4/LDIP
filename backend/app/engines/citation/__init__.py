"""Citation Engine for Act citation extraction and verification.

This module provides services for extracting Act citations from legal documents,
normalizing Act names, and tracking citation verification status.

Story 3-1: Act Citation Extraction
"""

from app.engines.citation.abbreviations import (
    ACT_ABBREVIATIONS,
    extract_year_from_name,
    get_canonical_name,
    get_display_name,
    normalize_act_name,
)
from app.engines.citation.extractor import (
    CitationExtractor,
    CitationExtractorError,
    CitationConfigurationError,
    get_citation_extractor,
)
from app.engines.citation.storage import (
    CitationStorageError,
    CitationStorageService,
    get_citation_storage_service,
)
from app.engines.citation.discovery import (
    ActDiscoveryService,
    get_act_discovery_service,
)

__all__ = [
    "ACT_ABBREVIATIONS",
    "ActDiscoveryService",
    "CitationConfigurationError",
    "CitationExtractor",
    "CitationExtractorError",
    "CitationStorageError",
    "CitationStorageService",
    "extract_year_from_name",
    "get_act_discovery_service",
    "get_canonical_name",
    "get_citation_extractor",
    "get_citation_storage_service",
    "get_display_name",
    "normalize_act_name",
]
