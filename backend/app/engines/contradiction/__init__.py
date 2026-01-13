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

from app.engines.contradiction.statement_query import (
    StatementQueryEngine,
    ValueExtractor,
    get_statement_query_engine,
    get_value_extractor,
)

__all__ = [
    "StatementQueryEngine",
    "ValueExtractor",
    "get_statement_query_engine",
    "get_value_extractor",
]
