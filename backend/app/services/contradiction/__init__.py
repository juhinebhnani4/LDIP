"""Contradiction services for statement querying and analysis.

Service layer for the Contradiction Engine (Epic 5).
"""

from app.services.contradiction.comparator import (
    StatementComparisonService,
    get_statement_comparison_service,
)
from app.services.contradiction.statement_query import (
    StatementQueryService,
    get_statement_query_service,
)

__all__ = [
    # Story 5-1
    "StatementQueryService",
    "get_statement_query_service",
    # Story 5-2
    "StatementComparisonService",
    "get_statement_comparison_service",
]
