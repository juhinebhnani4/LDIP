"""Contradiction List Service for Story 14.2.

Story 14.2: Contradictions List API Endpoint

Service for retrieving ALL contradictions for a matter, grouped by entity.
Uses statement_comparisons table as the source of truth.

CRITICAL: Uses Supabase service client - matter access validated at API layer.
"""

import asyncio
import math
from datetime import datetime
from functools import lru_cache
from typing import Any

import structlog

from app.models.contradiction import (
    ContradictionType,
    PaginationMeta,
    SeverityLevel,
)
from app.models.contradiction_list import (
    DEFAULT_PAGE_SIZE,
    MAX_EXCERPT_LENGTH,
    MAX_PAGE_SIZE,
    ContradictionEvidenceLink,
    ContradictionItem,
    ContradictionsListResponse,
    EntityContradictions,
    StatementInfo,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 14.2: Exceptions
# =============================================================================


class ContradictionListServiceError(Exception):
    """Base exception for contradiction list service operations."""

    def __init__(
        self,
        message: str,
        code: str = "CONTRADICTION_LIST_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class MatterNotFoundError(ContradictionListServiceError):
    """Raised when matter is not found."""

    def __init__(self, matter_id: str):
        super().__init__(
            message=f"Matter with ID {matter_id} not found",
            code="MATTER_NOT_FOUND",
            status_code=404,
        )


# =============================================================================
# Story 14.2: Contradiction List Service
# =============================================================================


class ContradictionListService:
    """Service for retrieving contradictions grouped by entity.

    Story 14.2: Implements AC #1-6 for the GET contradictions endpoint.

    Workflow:
    1. Query statement_comparisons WHERE result = 'contradiction'
    2. Join with identity_nodes for entity names
    3. Join with chunks for statement content
    4. Join with documents for document names
    5. Apply filters (severity, type, entity, document)
    6. Apply sorting (default: severity DESC, created_at DESC)
    7. Apply pagination
    8. Group results by entity

    Example:
        >>> service = ContradictionListService()
        >>> response = await service.get_all_contradictions("matter-123")
        >>> len(response.data)  # Number of entities with contradictions
        5
    """

    def __init__(self) -> None:
        """Initialize contradiction list service."""
        self._supabase_client = None

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            ContradictionListServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise ContradictionListServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    async def get_all_contradictions(
        self,
        matter_id: str,
        severity: str | None = None,
        contradiction_type: str | None = None,
        entity_id: str | None = None,
        document_id: str | None = None,
        page: int = 1,
        per_page: int = DEFAULT_PAGE_SIZE,
        sort_by: str = "severity",
        sort_order: str = "desc",
    ) -> ContradictionsListResponse:
        """Get all contradictions for a matter grouped by entity.

        Story 14.2: Main API for retrieving contradictions.

        Args:
            matter_id: Matter UUID.
            severity: Filter by severity (high/medium/low).
            contradiction_type: Filter by type (semantic_contradiction, etc.).
            entity_id: Filter to specific entity.
            document_id: Filter by source document.
            page: Page number (1-indexed).
            per_page: Items per page (max 100).
            sort_by: Sort field (severity, createdAt, entityName).
            sort_order: Sort direction (asc, desc).

        Returns:
            ContradictionsListResponse with entity-grouped contradictions.

        Raises:
            ContradictionListServiceError: If query fails.
        """
        logger.info(
            "contradiction_list_query_started",
            matter_id=matter_id,
            severity=severity,
            contradiction_type=contradiction_type,
            entity_id=entity_id,
            document_id=document_id,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Clamp per_page to max
        per_page = min(per_page, MAX_PAGE_SIZE)

        # Get total count for pagination
        total = await self._get_total_count(
            matter_id=matter_id,
            severity=severity,
            contradiction_type=contradiction_type,
            entity_id=entity_id,
            document_id=document_id,
        )

        # Calculate offset
        offset = (page - 1) * per_page

        # Return empty if no contradictions
        if total == 0:
            logger.info(
                "contradiction_list_empty",
                matter_id=matter_id,
            )
            return ContradictionsListResponse(
                data=[],
                meta=PaginationMeta(
                    total=0,
                    page=page,
                    per_page=per_page,
                    total_pages=0,
                ),
            )

        # Query contradictions
        contradictions = await self._query_contradictions(
            matter_id=matter_id,
            severity=severity,
            contradiction_type=contradiction_type,
            entity_id=entity_id,
            document_id=document_id,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=per_page,
            offset=offset,
        )

        # Group by entity
        entity_groups = self._group_by_entity(contradictions)

        total_pages = math.ceil(total / per_page) if total > 0 else 0

        logger.info(
            "contradiction_list_query_complete",
            matter_id=matter_id,
            total=total,
            entity_groups=len(entity_groups),
            page=page,
        )

        return ContradictionsListResponse(
            data=entity_groups,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    async def _get_total_count(
        self,
        matter_id: str,
        severity: str | None = None,
        contradiction_type: str | None = None,
        entity_id: str | None = None,
        document_id: str | None = None,
    ) -> int:
        """Get total count of contradictions matching filters.

        Args:
            matter_id: Matter UUID.
            severity: Optional severity filter.
            contradiction_type: Optional type filter.
            entity_id: Optional entity filter.
            document_id: Optional document filter.

        Returns:
            Total count.
        """
        try:
            query = (
                self.supabase.table("statement_comparisons")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
            )

            # Apply filters
            if severity:
                query = query.eq("severity", severity.lower())
            if contradiction_type:
                query = query.eq("contradiction_type", contradiction_type)
            if entity_id:
                query = query.eq("entity_id", entity_id)

            result = await asyncio.to_thread(lambda: query.execute())
            return result.count or 0

        except Exception as e:
            logger.error(
                "contradiction_count_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise ContradictionListServiceError(
                f"Failed to count contradictions: {e}",
                code="COUNT_FAILED",
            ) from e

    async def _query_contradictions(
        self,
        matter_id: str,
        severity: str | None = None,
        contradiction_type: str | None = None,
        entity_id: str | None = None,
        document_id: str | None = None,
        sort_by: str = "severity",
        sort_order: str = "desc",
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query contradictions with joins and filters.

        Args:
            matter_id: Matter UUID.
            severity: Optional severity filter.
            contradiction_type: Optional type filter.
            entity_id: Optional entity filter.
            document_id: Optional document filter.
            sort_by: Sort field.
            sort_order: Sort direction.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of contradiction dictionaries.
        """
        try:
            # Build base query with joins
            # Note: We need to query statement_comparisons and join related tables
            query = (
                self.supabase.table("statement_comparisons")
                .select(
                    "id, entity_id, contradiction_type, severity, explanation, "
                    "confidence, evidence, created_at, "
                    "statement_a_id, statement_b_id, "
                    "identity_nodes!statement_comparisons_entity_id_fkey(id, canonical_name)"
                )
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
            )

            # Apply filters
            if severity:
                query = query.eq("severity", severity.lower())
            if contradiction_type:
                query = query.eq("contradiction_type", contradiction_type)
            if entity_id:
                query = query.eq("entity_id", entity_id)

            # Apply sorting
            # Note: Supabase doesn't support custom CASE ordering,
            # so we order by field directly and post-process if needed
            desc = sort_order.lower() == "desc"

            if sort_by == "severity":
                query = query.order("severity", desc=desc)
                query = query.order("created_at", desc=True)
            elif sort_by == "createdAt":
                query = query.order("created_at", desc=desc)
            else:
                # Default sorting
                query = query.order("severity", desc=True)
                query = query.order("created_at", desc=True)

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            result = await asyncio.to_thread(lambda: query.execute())

            # Now fetch statement details for each contradiction
            contradictions = []
            for row in result.data or []:
                # Get statement details
                statement_a = await self._get_statement_details(row.get("statement_a_id"))
                statement_b = await self._get_statement_details(row.get("statement_b_id"))

                # Filter by document_id if provided
                if document_id:
                    doc_a_id = statement_a.get("document_id") if statement_a else None
                    doc_b_id = statement_b.get("document_id") if statement_b else None
                    if doc_a_id != document_id and doc_b_id != document_id:
                        continue

                entity_data = row.get("identity_nodes") or {}

                contradictions.append({
                    "id": row.get("id"),
                    "entity_id": row.get("entity_id"),
                    "entity_name": entity_data.get("canonical_name", "Unknown"),
                    "contradiction_type": row.get("contradiction_type"),
                    "severity": row.get("severity"),
                    "explanation": row.get("explanation", ""),
                    "confidence": row.get("confidence", 0.0),
                    "evidence": row.get("evidence"),
                    "created_at": row.get("created_at"),
                    "statement_a": statement_a,
                    "statement_b": statement_b,
                })

            return contradictions

        except ContradictionListServiceError:
            raise
        except Exception as e:
            logger.error(
                "contradiction_query_failed",
                error=str(e),
                matter_id=matter_id,
            )
            raise ContradictionListServiceError(
                f"Failed to query contradictions: {e}",
                code="QUERY_FAILED",
            ) from e

    async def _get_statement_details(
        self,
        chunk_id: str | None,
    ) -> dict[str, Any] | None:
        """Get statement details from chunks table.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            Statement details dict or None.
        """
        if not chunk_id:
            return None

        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("chunks")
                .select(
                    "id, content, page_number, document_id, "
                    "documents(id, name)"
                )
                .eq("chunk_id", chunk_id)
                .single()
                .execute()
            )

            row = result.data
            if not row:
                return None

            doc_data = row.get("documents") or {}

            return {
                "chunk_id": chunk_id,
                "content": row.get("content", ""),
                "page_number": row.get("page_number"),
                "document_id": row.get("document_id") or doc_data.get("id"),
                "document_name": doc_data.get("name", "Unknown"),
            }

        except Exception as e:
            logger.warning(
                "statement_details_failed",
                error=str(e),
                chunk_id=chunk_id,
            )
            return None

    def _group_by_entity(
        self,
        contradictions: list[dict[str, Any]],
    ) -> list[EntityContradictions]:
        """Group contradictions by entity.

        Args:
            contradictions: List of contradiction dicts.

        Returns:
            List of EntityContradictions.
        """
        # Group by entity_id
        entity_map: dict[str, list[dict]] = {}
        entity_names: dict[str, str] = {}

        for c in contradictions:
            eid = c.get("entity_id")
            if not eid:
                continue

            if eid not in entity_map:
                entity_map[eid] = []
                entity_names[eid] = c.get("entity_name", "Unknown")

            entity_map[eid].append(c)

        # Build response models
        result = []
        for eid, items in entity_map.items():
            contradiction_items = [
                self._build_contradiction_item(c) for c in items
            ]

            result.append(
                EntityContradictions(
                    entity_id=eid,
                    entity_name=entity_names[eid],
                    contradictions=contradiction_items,
                    count=len(contradiction_items),
                )
            )

        return result

    def _build_contradiction_item(
        self,
        data: dict[str, Any],
    ) -> ContradictionItem:
        """Build ContradictionItem from raw data.

        Args:
            data: Raw contradiction dict.

        Returns:
            ContradictionItem model.
        """
        statement_a = data.get("statement_a") or {}
        statement_b = data.get("statement_b") or {}
        evidence = data.get("evidence") or {}

        # Build statement info
        stmt_a_info = StatementInfo(
            document_id=statement_a.get("document_id", ""),
            document_name=statement_a.get("document_name", "Unknown"),
            page=statement_a.get("page_number"),
            excerpt=self._truncate_excerpt(statement_a.get("content", "")),
            date=evidence.get("value_a"),  # Extract date if available
        )

        stmt_b_info = StatementInfo(
            document_id=statement_b.get("document_id", ""),
            document_name=statement_b.get("document_name", "Unknown"),
            page=statement_b.get("page_number"),
            excerpt=self._truncate_excerpt(statement_b.get("content", "")),
            date=evidence.get("value_b"),  # Extract date if available
        )

        # Build evidence links
        evidence_links = []
        if statement_a.get("chunk_id"):
            evidence_links.append(
                ContradictionEvidenceLink(
                    statement_id=statement_a["chunk_id"],
                    document_id=statement_a.get("document_id", ""),
                    document_name=statement_a.get("document_name", "Unknown"),
                    page=statement_a.get("page_number"),
                    bbox_ids=[],  # TODO: Add bbox lookup when available
                )
            )
        if statement_b.get("chunk_id"):
            evidence_links.append(
                ContradictionEvidenceLink(
                    statement_id=statement_b["chunk_id"],
                    document_id=statement_b.get("document_id", ""),
                    document_name=statement_b.get("document_name", "Unknown"),
                    page=statement_b.get("page_number"),
                    bbox_ids=[],
                )
            )

        # Parse contradiction type
        raw_type = data.get("contradiction_type", "semantic_contradiction")
        try:
            c_type = ContradictionType(raw_type)
        except ValueError:
            c_type = ContradictionType.SEMANTIC_CONTRADICTION

        # Parse severity
        raw_severity = data.get("severity", "medium")
        try:
            severity = SeverityLevel(raw_severity.lower())
        except ValueError:
            severity = SeverityLevel.MEDIUM

        # Format created_at
        created_at = data.get("created_at", "")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        return ContradictionItem(
            id=data.get("id", ""),
            contradiction_type=c_type,
            severity=severity,
            entity_id=data.get("entity_id", ""),
            entity_name=data.get("entity_name", "Unknown"),
            statement_a=stmt_a_info,
            statement_b=stmt_b_info,
            explanation=data.get("explanation", ""),
            evidence_links=evidence_links,
            confidence=float(data.get("confidence", 0.0)),
            created_at=created_at,
        )

    def _truncate_excerpt(self, content: str) -> str:
        """Truncate content to max excerpt length.

        Args:
            content: Full content string.

        Returns:
            Truncated excerpt.
        """
        if len(content) <= MAX_EXCERPT_LENGTH:
            return content
        return content[: MAX_EXCERPT_LENGTH - 3] + "..."


# =============================================================================
# Story 14.2: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_contradiction_list_service() -> ContradictionListService:
    """Get singleton contradiction list service instance.

    Returns:
        ContradictionListService instance.
    """
    return ContradictionListService()
