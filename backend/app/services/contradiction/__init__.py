"""Contradiction services for statement querying and analysis.

Service layer for the Contradiction Engine (Epic 5).
"""

from app.services.contradiction.statement_query import (
    StatementQueryService,
    get_statement_query_service,
)

__all__ = [
    "StatementQueryService",
    "get_statement_query_service",
]
