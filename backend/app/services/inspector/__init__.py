"""Inspector service for RAG pipeline debugging.

Story: RAG Production Gaps - Feature 3: Inspector Mode
Provides detailed timing and scoring information for search debugging.
"""

from app.services.inspector.inspector_service import (
    InspectorService,
    get_inspector_service,
)

__all__ = [
    "InspectorService",
    "get_inspector_service",
]
