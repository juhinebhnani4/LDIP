"""Citation extraction modules."""

from .extractor import CitationExtractor, extract_citations
from .patterns import CITATION_PATTERNS
from .abbreviations import ACT_ABBREVIATIONS, resolve_abbreviation

__all__ = [
    "CitationExtractor",
    "extract_citations",
    "CITATION_PATTERNS",
    "ACT_ABBREVIATIONS",
    "resolve_abbreviation",
]
