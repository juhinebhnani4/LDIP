"""Contradiction Engine for detecting inconsistencies across documents.

Epic 5: Consistency & Contradiction Engine

Pipeline stages:
1. Statement Querying (Story 5-1) - Group statements by entity
2. Pair Comparison (Story 5-2) - Compare statement pairs with GPT-4
3. Classification (Story 5-3) - Classify contradiction types
4. Severity Scoring (Story 5-4) - Score severity and generate explanations

This module provides the engine components for detecting contradictions
and inconsistencies in legal documents.
"""

from app.engines.contradiction.classifier import (
    ContradictionClassifier,
    get_contradiction_classifier,
)
from app.engines.contradiction.comparator import (
    ComparisonBatchResult,
    LLMCostTracker,
    StatementComparator,
    StatementPair,
    get_statement_comparator,
)
from app.engines.contradiction.scorer import (
    ContradictionScorer,
    get_contradiction_scorer,
)
from app.engines.contradiction.statement_query import (
    StatementQueryEngine,
    ValueExtractor,
    get_statement_query_engine,
    get_value_extractor,
)

__all__ = [
    # Story 5-1
    "StatementQueryEngine",
    "ValueExtractor",
    "get_statement_query_engine",
    "get_value_extractor",
    # Story 5-2
    "ComparisonBatchResult",
    "LLMCostTracker",
    "StatementComparator",
    "StatementPair",
    "get_statement_comparator",
    # Story 5-3
    "ContradictionClassifier",
    "get_contradiction_classifier",
    # Story 5-4
    "ContradictionScorer",
    "get_contradiction_scorer",
]
