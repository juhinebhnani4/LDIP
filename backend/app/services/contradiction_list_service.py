"""Contradiction List Service for Story 14.2.

Story 14.2: Contradictions List API Endpoint

Service for retrieving ALL contradictions for a matter, grouped by entity.
Uses statement_comparisons table as the source of truth.

CRITICAL: Uses Supabase service client - matter access validated at API layer.
"""

import asyncio
import math
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

        # Get total count for pagination (includes document filter)
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

        # Query contradictions with all data in single query (no N+1)
        contradictions = await self._query_contradictions_with_statements(
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
            # For document_id filter, we need to count via RPC or subquery
            # Since Supabase doesn't support easy subqueries, we use a different approach
            if document_id:
                # Get IDs of contradictions where either statement is in the document
                return await self._get_count_with_document_filter(
                    matter_id=matter_id,
                    severity=severity,
                    contradiction_type=contradiction_type,
                    entity_id=entity_id,
                    document_id=document_id,
                )

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

        except ContradictionListServiceError:
            raise
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

    async def _get_count_with_document_filter(
        self,
        matter_id: str,
        severity: str | None,
        contradiction_type: str | None,
        entity_id: str | None,
        document_id: str,
    ) -> int:
        """Get count when document filter is applied.

        Uses a workaround since Supabase doesn't support easy subqueries.
        Fetches chunk IDs for the document and filters comparisons.

        Args:
            matter_id: Matter UUID.
            severity: Optional severity filter.
            contradiction_type: Optional type filter.
            entity_id: Optional entity filter.
            document_id: Document UUID to filter by.

        Returns:
            Total count matching filters including document.
        """
        try:
            # First, get all chunk IDs for the document
            chunks_result = await asyncio.to_thread(
                lambda: self.supabase.table("chunks")
                .select("chunk_id")
                .eq("document_id", document_id)
                .execute()
            )
            chunk_ids = [c["chunk_id"] for c in (chunks_result.data or [])]

            if not chunk_ids:
                return 0

            # Now count contradictions where either statement is in those chunks
            # We need to do this in two queries and dedupe
            query_a = (
                self.supabase.table("statement_comparisons")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
                .in_("statement_a_id", chunk_ids)
            )

            query_b = (
                self.supabase.table("statement_comparisons")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
                .in_("statement_b_id", chunk_ids)
            )

            # Apply other filters
            if severity:
                query_a = query_a.eq("severity", severity.lower())
                query_b = query_b.eq("severity", severity.lower())
            if contradiction_type:
                query_a = query_a.eq("contradiction_type", contradiction_type)
                query_b = query_b.eq("contradiction_type", contradiction_type)
            if entity_id:
                query_a = query_a.eq("entity_id", entity_id)
                query_b = query_b.eq("entity_id", entity_id)

            # For accurate count, we need the actual IDs to dedupe
            # Get IDs from both
            ids_query_a = (
                self.supabase.table("statement_comparisons")
                .select("id")
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
                .in_("statement_a_id", chunk_ids)
            )
            ids_query_b = (
                self.supabase.table("statement_comparisons")
                .select("id")
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
                .in_("statement_b_id", chunk_ids)
            )

            if severity:
                ids_query_a = ids_query_a.eq("severity", severity.lower())
                ids_query_b = ids_query_b.eq("severity", severity.lower())
            if contradiction_type:
                ids_query_a = ids_query_a.eq("contradiction_type", contradiction_type)
                ids_query_b = ids_query_b.eq("contradiction_type", contradiction_type)
            if entity_id:
                ids_query_a = ids_query_a.eq("entity_id", entity_id)
                ids_query_b = ids_query_b.eq("entity_id", entity_id)

            ids_result_a = await asyncio.to_thread(lambda: ids_query_a.execute())
            ids_result_b = await asyncio.to_thread(lambda: ids_query_b.execute())

            # Combine and dedupe
            all_ids = set()
            for row in ids_result_a.data or []:
                all_ids.add(row["id"])
            for row in ids_result_b.data or []:
                all_ids.add(row["id"])

            return len(all_ids)

        except Exception as e:
            logger.error(
                "contradiction_count_with_doc_filter_failed",
                error=str(e),
                matter_id=matter_id,
                document_id=document_id,
            )
            raise ContradictionListServiceError(
                f"Failed to count contradictions with document filter: {e}",
                code="COUNT_FAILED",
            ) from e

    async def _query_contradictions_with_statements(
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
        """Query contradictions with all statement data in optimized queries.

        This method eliminates N+1 queries by:
        1. Fetching all contradictions in one query
        2. Batching all chunk lookups into a single query
        3. Building the complete response from the batched data

        Args:
            matter_id: Matter UUID.
            severity: Optional severity filter.
            contradiction_type: Optional type filter.
            entity_id: Optional entity filter.
            document_id: Optional document filter.
            sort_by: Sort field (severity, createdAt, entityName).
            sort_order: Sort direction.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of contradiction dictionaries with statement data.
        """
        try:
            # Step 1: Get contradiction IDs if document filter is applied
            contradiction_ids: list[str] | None = None
            if document_id:
                contradiction_ids = await self._get_contradiction_ids_for_document(
                    matter_id=matter_id,
                    severity=severity,
                    contradiction_type=contradiction_type,
                    entity_id=entity_id,
                    document_id=document_id,
                )
                if not contradiction_ids:
                    return []

            # Step 2: Build main query (no FK join - fetch entity names separately)
            query = (
                self.supabase.table("statement_comparisons")
                .select(
                    "id, entity_id, contradiction_type, severity, explanation, "
                    "confidence, evidence, created_at, "
                    "statement_a_id, statement_b_id"
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
            if contradiction_ids is not None:
                query = query.in_("id", contradiction_ids)

            # Apply sorting (entityName sorting handled post-query since no FK join)
            desc = sort_order.lower() == "desc"
            if sort_by == "severity":
                query = query.order("severity", desc=desc)
                query = query.order("created_at", desc=True)
            elif sort_by == "createdAt":
                query = query.order("created_at", desc=desc)
            elif sort_by == "entityName":
                # Sort by entity_id for now; post-sort by name after fetching
                query = query.order("entity_id", desc=desc)
                query = query.order("created_at", desc=True)
            else:
                # Default sorting
                query = query.order("severity", desc=True)
                query = query.order("created_at", desc=True)

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            result = await asyncio.to_thread(lambda: query.execute())
            rows = result.data or []

            if not rows:
                return []

            # Step 3: Collect all chunk IDs and entity IDs for batch lookup
            chunk_ids: set[str] = set()
            entity_ids: set[str] = set()
            for row in rows:
                if row.get("statement_a_id"):
                    chunk_ids.add(row["statement_a_id"])
                if row.get("statement_b_id"):
                    chunk_ids.add(row["statement_b_id"])
                if row.get("entity_id"):
                    entity_ids.add(row["entity_id"])

            # Step 4: Batch fetch all chunks with document info
            chunks_map = await self._batch_get_statement_details(list(chunk_ids))

            # Step 5: Batch fetch entity names
            entity_names_map = await self._batch_get_entity_names(list(entity_ids))

            # Step 6: Build contradiction list with statement data
            contradictions: list[dict[str, Any]] = []
            for row in rows:
                entity_id = row.get("entity_id", "")
                statement_a = chunks_map.get(row.get("statement_a_id", ""))
                statement_b = chunks_map.get(row.get("statement_b_id", ""))

                contradictions.append({
                    "id": row.get("id"),
                    "entity_id": entity_id,
                    "entity_name": entity_names_map.get(entity_id, "Unknown"),
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

    async def _get_contradiction_ids_for_document(
        self,
        matter_id: str,
        severity: str | None,
        contradiction_type: str | None,
        entity_id: str | None,
        document_id: str,
    ) -> list[str]:
        """Get contradiction IDs where either statement is from the specified document.

        Args:
            matter_id: Matter UUID.
            severity: Optional severity filter.
            contradiction_type: Optional type filter.
            entity_id: Optional entity filter.
            document_id: Document UUID to filter by.

        Returns:
            List of contradiction IDs matching the document filter.
        """
        # Get chunk IDs for the document
        chunks_result = await asyncio.to_thread(
            lambda: self.supabase.table("chunks")
            .select("chunk_id")
            .eq("document_id", document_id)
            .execute()
        )
        chunk_ids = [c["chunk_id"] for c in (chunks_result.data or [])]

        if not chunk_ids:
            return []

        # Get contradictions where statement_a or statement_b is in those chunks
        ids_query_a = (
            self.supabase.table("statement_comparisons")
            .select("id")
            .eq("matter_id", matter_id)
            .eq("result", "contradiction")
            .in_("statement_a_id", chunk_ids)
        )
        ids_query_b = (
            self.supabase.table("statement_comparisons")
            .select("id")
            .eq("matter_id", matter_id)
            .eq("result", "contradiction")
            .in_("statement_b_id", chunk_ids)
        )

        if severity:
            ids_query_a = ids_query_a.eq("severity", severity.lower())
            ids_query_b = ids_query_b.eq("severity", severity.lower())
        if contradiction_type:
            ids_query_a = ids_query_a.eq("contradiction_type", contradiction_type)
            ids_query_b = ids_query_b.eq("contradiction_type", contradiction_type)
        if entity_id:
            ids_query_a = ids_query_a.eq("entity_id", entity_id)
            ids_query_b = ids_query_b.eq("entity_id", entity_id)

        ids_result_a = await asyncio.to_thread(lambda: ids_query_a.execute())
        ids_result_b = await asyncio.to_thread(lambda: ids_query_b.execute())

        # Combine and dedupe
        all_ids: set[str] = set()
        for row in ids_result_a.data or []:
            all_ids.add(row["id"])
        for row in ids_result_b.data or []:
            all_ids.add(row["id"])

        return list(all_ids)

    async def _batch_get_statement_details(
        self,
        chunk_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Batch fetch statement details for multiple chunks.

        Args:
            chunk_ids: List of chunk UUIDs.

        Returns:
            Dictionary mapping chunk_id to statement details.
        """
        if not chunk_ids:
            return {}

        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("chunks")
                .select(
                    "id, content, page_number, document_id, "
                    "documents(id, filename)"
                )
                .in_("id", chunk_ids)
                .execute()
            )

            chunks_map: dict[str, dict[str, Any]] = {}
            for row in result.data or []:
                doc_data = row.get("documents") or {}
                chunk_id = row.get("id")
                if chunk_id:
                    chunks_map[chunk_id] = {
                        "chunk_id": chunk_id,
                        "content": row.get("content", ""),
                        "page_number": row.get("page_number"),
                        "document_id": row.get("document_id") or doc_data.get("id"),
                        "document_name": doc_data.get("filename", "Unknown"),
                    }

            return chunks_map

        except Exception as e:
            logger.warning(
                "batch_statement_details_failed",
                error=str(e),
                chunk_count=len(chunk_ids),
            )
            return {}

    async def _batch_get_entity_names(
        self,
        entity_ids: list[str],
    ) -> dict[str, str]:
        """Batch fetch entity names from identity_nodes.

        Args:
            entity_ids: List of entity UUIDs.

        Returns:
            Dictionary mapping entity_id to canonical_name.
        """
        if not entity_ids:
            return {}

        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("identity_nodes")
                .select("id, canonical_name")
                .in_("id", entity_ids)
                .execute()
            )

            entity_names: dict[str, str] = {}
            for row in result.data or []:
                entity_id = row.get("id")
                if entity_id:
                    entity_names[entity_id] = row.get("canonical_name", "Unknown")

            return entity_names

        except Exception as e:
            logger.warning(
                "batch_entity_names_failed",
                error=str(e),
                entity_count=len(entity_ids),
            )
            return {}

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
        entity_map: dict[str, list[dict[str, Any]]] = {}
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
        result: list[EntityContradictions] = []
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
        statement_a: dict[str, Any] = data.get("statement_a") or {}
        statement_b: dict[str, Any] = data.get("statement_b") or {}
        evidence: dict[str, Any] = data.get("evidence") or {}

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

        # Build evidence links (bbox_ids populated when bbox data is available)
        evidence_links: list[ContradictionEvidenceLink] = []
        if statement_a.get("chunk_id"):
            evidence_links.append(
                ContradictionEvidenceLink(
                    statement_id=statement_a["chunk_id"],
                    document_id=statement_a.get("document_id", ""),
                    document_name=statement_a.get("document_name", "Unknown"),
                    page=statement_a.get("page_number"),
                    bbox_ids=[],
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
            severity = SeverityLevel(raw_severity.lower() if raw_severity else "medium")
        except ValueError:
            severity = SeverityLevel.MEDIUM

        # Format created_at - handle both string and datetime objects
        created_at = data.get("created_at", "")
        if created_at and hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        elif not isinstance(created_at, str):
            created_at = str(created_at) if created_at else ""

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
