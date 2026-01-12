"""MIG (Matter Identity Graph) services module.

This module provides entity extraction and graph management for legal documents.
Extracts people, organizations, institutions, and assets mentioned in documents
and maintains their relationships within a matter.

Services:
- MIGEntityExtractor: Extract entities from document text using Gemini
- MIGGraphService: CRUD operations for entity nodes, edges, and mentions
"""

from app.services.mig.extractor import MIGEntityExtractor, get_mig_extractor
from app.services.mig.graph import MIGGraphService, get_mig_graph_service

__all__ = [
    "MIGEntityExtractor",
    "MIGGraphService",
    "get_mig_extractor",
    "get_mig_graph_service",
]
