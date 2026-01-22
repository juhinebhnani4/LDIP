"""Table extraction service using Docling.

Extracts tables from PDF documents during ingestion,
converts them to Markdown format for better retrieval.
"""

from app.services.table_extraction.extractor import (
    TableExtractor,
    get_table_extractor,
)
from app.services.table_extraction.models import (
    ExtractedTable,
    TableExtractionResult,
)

__all__ = [
    "TableExtractor",
    "get_table_extractor",
    "ExtractedTable",
    "TableExtractionResult",
]
