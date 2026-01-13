"""Citation Engine for Act citation extraction and verification.

This module provides services for extracting Act citations from legal documents,
normalizing Act names, tracking citation verification status, and verifying
citations against uploaded Act documents.

Story 3-1: Act Citation Extraction
Story 3-3: Citation Verification
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
from app.engines.citation.act_indexer import (
    ActIndexer,
    ActIndexerError,
    ActNotIndexedError,
    get_act_indexer,
)
from app.engines.citation.verifier import (
    CitationVerifier,
    CitationVerificationError,
    SectionNotFoundError,
    QuoteComparisonError,
    VerificationConfigurationError,
    get_citation_verifier,
)

__all__ = [
    # Abbreviations
    "ACT_ABBREVIATIONS",
    "extract_year_from_name",
    "get_canonical_name",
    "get_display_name",
    "normalize_act_name",
    # Extractor
    "CitationConfigurationError",
    "CitationExtractor",
    "CitationExtractorError",
    "get_citation_extractor",
    # Storage
    "CitationStorageError",
    "CitationStorageService",
    "get_citation_storage_service",
    # Discovery
    "ActDiscoveryService",
    "get_act_discovery_service",
    # Act Indexer (Story 3-3)
    "ActIndexer",
    "ActIndexerError",
    "ActNotIndexedError",
    "get_act_indexer",
    # Verifier (Story 3-3)
    "CitationVerifier",
    "CitationVerificationError",
    "SectionNotFoundError",
    "QuoteComparisonError",
    "VerificationConfigurationError",
    "get_citation_verifier",
]
