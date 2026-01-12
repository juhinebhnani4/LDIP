"""MIG (Matter Identity Graph) services module.

This module provides entity extraction and graph management for legal documents.
Extracts people, organizations, institutions, and assets mentioned in documents
and maintains their relationships within a matter.

Services:
- MIGEntityExtractor: Extract entities from document text using Gemini
- MIGGraphService: CRUD operations for entity nodes, edges, and mentions
- EntityResolver: Alias resolution and name similarity for entity linking
- CorrectionLearningService: Track and learn from user corrections
"""

from app.services.mig.correction_learning import (
    AliasCorrection,
    CorrectionLearningService,
    CorrectionStats,
    get_correction_learning_service,
)
from app.services.mig.entity_resolver import (
    AliasCandidate,
    AliasResolutionResult,
    EntityResolver,
    NameComponents,
    get_entity_resolver,
)
from app.services.mig.extractor import MIGEntityExtractor, get_mig_extractor
from app.services.mig.graph import MIGGraphService, get_mig_graph_service

__all__ = [
    "MIGEntityExtractor",
    "MIGGraphService",
    "EntityResolver",
    "CorrectionLearningService",
    "AliasCandidate",
    "AliasCorrection",
    "AliasResolutionResult",
    "CorrectionStats",
    "NameComponents",
    "get_mig_extractor",
    "get_mig_graph_service",
    "get_entity_resolver",
    "get_correction_learning_service",
]
