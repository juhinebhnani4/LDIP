"""Global Search Service for cross-matter search.

This module implements search across ALL matters a user has access to.
Uses the existing HybridSearchService for per-matter search and merges
results using cross-matter RRF.

CRITICAL: Matter isolation is enforced by:
1. Querying matter_attorneys to get accessible matter IDs
2. Using HybridSearchService which validates namespace per-matter
"""

import asyncio
from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.models.global_search import (
    GlobalSearchMeta,
    GlobalSearchResponse,
    GlobalSearchResultItem,
)
from app.services.rag.hybrid_search import (
    HybridSearchService,
    HybridSearchServiceError,
    SearchResult,
    get_hybrid_search_service,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)

# Per-matter search limit (top N from each matter)
PER_MATTER_LIMIT = 10
# Default global search limit
DEFAULT_GLOBAL_LIMIT = 20
# Maximum global search limit
MAX_GLOBAL_LIMIT = 50
# Minimum query length
MIN_QUERY_LENGTH = 2
# RRF constant for cross-matter merge
RRF_K = 60


class GlobalSearchServiceError(Exception):
    """Exception for global search service errors."""

    def __init__(
        self,
        message: str,
        code: str = "GLOBAL_SEARCH_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


@dataclass
class MatterInfo:
    """Information about a matter for search results."""

    id: str
    title: str
    description: str | None


@dataclass
class SearchResultWithMatter:
    """Search result with matter information."""

    result: SearchResult
    matter: MatterInfo
    source_rank: int  # Rank within source matter


class GlobalSearchService:
    """Service for searching across all user-accessible matters.

    Implements cross-matter hybrid search by:
    1. Getting all matter IDs user has access to
    2. Executing parallel hybrid searches per matter
    3. Merging results using RRF across all matters
    4. Also matching matter titles for direct matter results

    CRITICAL: This service enforces matter isolation by querying
    the matter_attorneys table for accessible matters.
    """

    def __init__(
        self,
        hybrid_search: HybridSearchService | None = None,
    ):
        """Initialize global search service.

        Args:
            hybrid_search: Optional HybridSearchService instance.
        """
        self.hybrid_search = hybrid_search or get_hybrid_search_service()

    async def _get_accessible_matters(self, user_id: str) -> list[MatterInfo]:
        """Get all matters the user has access to.

        Args:
            user_id: User ID to check access for.

        Returns:
            List of MatterInfo with id, title, description.

        Raises:
            GlobalSearchServiceError: If database query fails.
        """
        try:
            supabase = get_supabase_client()
            if supabase is None:
                raise GlobalSearchServiceError(
                    message="Database client not configured",
                    code="DATABASE_NOT_CONFIGURED",
                    is_retryable=False,
                )

            # Query matter_attorneys to get accessible matter IDs
            # Then join with matters table to get titles
            response = supabase.table("matter_attorneys").select(
                "matter_id, matters(id, title, description)"
            ).eq("user_id", user_id).execute()

            if not response.data:
                return []

            matters = []
            for row in response.data:
                matter_data = row.get("matters")
                if matter_data:
                    matters.append(MatterInfo(
                        id=matter_data["id"],
                        title=matter_data.get("title", ""),
                        description=matter_data.get("description"),
                    ))

            logger.debug(
                "accessible_matters_found",
                user_id=user_id,
                matter_count=len(matters),
            )

            return matters

        except GlobalSearchServiceError:
            raise
        except Exception as e:
            logger.error(
                "get_accessible_matters_failed",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise GlobalSearchServiceError(
                message=f"Failed to get accessible matters: {e!s}",
                code="DATABASE_ERROR",
                is_retryable=True,
            ) from e

    async def _search_single_matter(
        self,
        query: str,
        matter: MatterInfo,
        limit: int,
    ) -> list[SearchResultWithMatter]:
        """Search a single matter and wrap results with matter info.

        Args:
            query: Search query.
            matter: Matter to search.
            limit: Max results per matter.

        Returns:
            List of SearchResultWithMatter or empty list on error.
        """
        try:
            result = await self.hybrid_search.search(
                query=query,
                matter_id=matter.id,
                limit=limit,
            )

            return [
                SearchResultWithMatter(
                    result=r,
                    matter=matter,
                    source_rank=idx + 1,
                )
                for idx, r in enumerate(result.results)
            ]

        except HybridSearchServiceError as e:
            # Log error but continue with other matters (partial results OK)
            logger.warning(
                "matter_search_failed",
                matter_id=matter.id,
                error=e.message,
                error_code=e.code,
            )
            return []
        except Exception as e:
            logger.warning(
                "matter_search_unexpected_error",
                matter_id=matter.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    def _match_matter_titles(
        self,
        query: str,
        matters: list[MatterInfo],
        limit: int = 5,
    ) -> list[GlobalSearchResultItem]:
        """Match query against matter titles.

        Args:
            query: Search query.
            matters: List of accessible matters.
            limit: Max matter results.

        Returns:
            List of GlobalSearchResultItem for matching matters.
        """
        query_lower = query.lower()
        matched = []

        for matter in matters:
            if query_lower in matter.title.lower():
                matched.append(GlobalSearchResultItem(
                    id=matter.id,
                    type="matter",
                    title=matter.title,
                    matter_id=matter.id,
                    matter_title=matter.title,
                    matched_content=(matter.description or "")[:100] if matter.description else "",
                ))

            if len(matched) >= limit:
                break

        return matched

    def _extract_match_snippet(
        self,
        content: str,
        query: str,
        max_length: int = 100,
    ) -> str:
        """Extract a snippet of content around the query match.

        Args:
            content: Full content text.
            query: Search query to find.
            max_length: Maximum snippet length.

        Returns:
            Snippet of content centered around the first match,
            or the beginning of content if no match found.
        """
        if not content:
            return ""

        content_lower = content.lower()
        query_lower = query.lower()

        # Try to find the query or any word from the query
        match_pos = content_lower.find(query_lower)
        if match_pos == -1:
            # Try individual words from the query
            for word in query_lower.split():
                if len(word) >= 3:  # Skip short words
                    match_pos = content_lower.find(word)
                    if match_pos != -1:
                        break

        if match_pos == -1:
            # No match found, return beginning
            return content[:max_length] if len(content) > max_length else content

        # Calculate snippet bounds centered on the match
        half_length = max_length // 2
        start = max(0, match_pos - half_length)
        end = min(len(content), start + max_length)

        # Adjust start if we're near the end
        if end - start < max_length:
            start = max(0, end - max_length)

        snippet = content[start:end]

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet[3:]
        if end < len(content):
            snippet = snippet[:-3] + "..."

        return snippet

    def _merge_results_rrf(
        self,
        all_results: list[SearchResultWithMatter],
        matters: list[MatterInfo],
        query: str,
        limit: int,
    ) -> list[GlobalSearchResultItem]:
        """Merge results from multiple matters using RRF.

        Args:
            all_results: All search results from all matters.
            matters: List of all accessible matters.
            query: Original search query.
            limit: Max results to return.

        Returns:
            List of GlobalSearchResultItem sorted by RRF score.
        """
        # Calculate cross-matter RRF score
        # rrf_score = 1 / (k + rank)
        scored_results: list[tuple[float, SearchResultWithMatter]] = []

        for result_with_matter in all_results:
            rrf_score = 1.0 / (RRF_K + result_with_matter.source_rank)
            scored_results.append((rrf_score, result_with_matter))

        # Sort by RRF score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Get matter title matches first
        matter_results = self._match_matter_titles(query, matters, limit=5)

        # Convert document results to GlobalSearchResultItem
        document_results: list[GlobalSearchResultItem] = []
        seen_ids: set[str] = set()

        # Track matter IDs from matter results to avoid duplicates
        matter_ids_in_results = {r.id for r in matter_results}

        for _score, result_with_matter in scored_results:
            if result_with_matter.result.id in seen_ids:
                continue
            seen_ids.add(result_with_matter.result.id)

            # Extract snippet around the query match (50-100 chars)
            content = result_with_matter.result.content
            snippet = self._extract_match_snippet(content, query, max_length=100)

            document_results.append(GlobalSearchResultItem(
                id=result_with_matter.result.document_id,  # Use document_id, not chunk id
                type="document",
                title=f"Document (Page {result_with_matter.result.page_number or 'N/A'})",
                matter_id=result_with_matter.matter.id,
                matter_title=result_with_matter.matter.title,
                matched_content=snippet,
            ))

            if len(document_results) >= limit:
                break

        # Combine: matter results first, then document results
        # Filter matter results to stay within limit
        combined = matter_results[:min(len(matter_results), 5)]
        remaining = limit - len(combined)
        combined.extend(document_results[:remaining])

        return combined

    async def search_across_matters(
        self,
        user_id: str,
        query: str,
        limit: int = DEFAULT_GLOBAL_LIMIT,
    ) -> GlobalSearchResponse:
        """Search across all matters the user has access to.

        Args:
            user_id: User ID for access control.
            query: Search query text.
            limit: Max results to return (default 20, max 50).

        Returns:
            GlobalSearchResponse with merged results.

        Raises:
            GlobalSearchServiceError: If search fails.
        """
        # Validate query length
        if len(query.strip()) < MIN_QUERY_LENGTH:
            return GlobalSearchResponse(
                data=[],
                meta=GlobalSearchMeta(query=query, total=0),
            )

        # Clamp limit
        limit = min(max(1, limit), MAX_GLOBAL_LIMIT)

        logger.info(
            "global_search_start",
            user_id=user_id,
            query_len=len(query),
            limit=limit,
        )

        try:
            # Step 1: Get all accessible matters
            matters = await self._get_accessible_matters(user_id)

            if not matters:
                logger.debug(
                    "global_search_no_matters",
                    user_id=user_id,
                )
                return GlobalSearchResponse(
                    data=[],
                    meta=GlobalSearchMeta(query=query, total=0),
                )

            # Step 2: Search all matters in parallel
            search_tasks = [
                self._search_single_matter(query, matter, PER_MATTER_LIMIT)
                for matter in matters
            ]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Flatten results, filtering out exceptions
            all_results: list[SearchResultWithMatter] = []
            for result in search_results:
                if isinstance(result, list):
                    all_results.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(
                        "matter_search_exception",
                        error=str(result),
                        error_type=type(result).__name__,
                    )

            # Step 3: Merge results with cross-matter RRF
            merged_results = self._merge_results_rrf(
                all_results=all_results,
                matters=matters,
                query=query,
                limit=limit,
            )

            logger.info(
                "global_search_complete",
                user_id=user_id,
                query_len=len(query),
                matters_searched=len(matters),
                results_found=len(merged_results),
            )

            return GlobalSearchResponse(
                data=merged_results,
                meta=GlobalSearchMeta(query=query, total=len(merged_results)),
            )

        except GlobalSearchServiceError:
            raise
        except Exception as e:
            logger.error(
                "global_search_failed",
                user_id=user_id,
                query_len=len(query),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise GlobalSearchServiceError(
                message=f"Global search failed: {e!s}",
                code="SEARCH_FAILED",
                is_retryable=True,
            ) from e


@lru_cache(maxsize=1)
def get_global_search_service() -> GlobalSearchService:
    """Get singleton global search service instance.

    Returns:
        GlobalSearchService instance.
    """
    return GlobalSearchService()
