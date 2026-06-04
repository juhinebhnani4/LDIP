"""User-facing Usage Statistics API.

Provides usage metrics (documents, pages, queries) without exposing
raw cost data (INR, USD, tokens, providers). Cost data is admin-only.

Endpoints:
- GET /api/usage/summary - Get usage summary across all user's matters
"""

import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.rate_limit import READONLY_RATE_LIMIT, limiter
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_supabase_client

router = APIRouter(prefix="/usage", tags=["usage"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class MatterUsageStats(BaseModel):
    """Usage stats for a single matter."""

    model_config = ConfigDict(populate_by_name=True)

    matter_id: str = Field(..., alias="matterId")
    matter_title: str = Field(..., alias="matterTitle")
    documents: int = Field(0, ge=0)
    pages: int = Field(0, ge=0)
    queries: int = Field(0, ge=0)


class UsageSummary(BaseModel):
    """Aggregated usage summary across all user's matters."""

    model_config = ConfigDict(populate_by_name=True)

    total_documents: int = Field(0, alias="totalDocuments", ge=0)
    total_pages: int = Field(0, alias="totalPages", ge=0)
    total_queries: int = Field(0, alias="totalQueries", ge=0)
    total_matters: int = Field(0, alias="totalMatters", ge=0)
    matters: list[MatterUsageStats] = Field(default_factory=list)


class UsageSummaryResponse(BaseModel):
    """API response wrapper for usage summary."""

    data: UsageSummary


# =============================================================================
# Endpoint
# =============================================================================


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    response_model_by_alias=True,
    summary="Get Usage Summary",
    description="""
    Get usage summary across all user's matters.

    Returns document counts, page counts, and query counts per matter.
    Does NOT expose cost data (INR, USD, tokens) — that is admin-only.

    **Requires authentication.**
    """,
)
@limiter.limit(READONLY_RATE_LIMIT)
async def get_usage_summary(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UsageSummaryResponse:
    """Get usage summary for the authenticated user."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Database not configured",
                        "details": {},
                    }
                },
            )

        # Step 1: Get user's matter IDs and titles
        matter_result = await asyncio.to_thread(
            lambda: supabase.table("matter_attorneys")
            .select("matter_id, matters(id, title, status, deleted_at)")
            .eq("user_id", current_user.id)
            .execute()
        )

        if not matter_result.data:
            return UsageSummaryResponse(data=UsageSummary())

        # Filter to active matters only
        active_matters: list[dict] = []
        for row in matter_result.data:
            matter = row.get("matters")
            if (
                matter
                and matter.get("status") != "archived"
                and not matter.get("deleted_at")
            ):
                active_matters.append(
                    {
                        "matter_id": row["matter_id"],
                        "title": matter.get("title", "Untitled"),
                    }
                )

        if not active_matters:
            return UsageSummaryResponse(data=UsageSummary())

        matter_ids = [m["matter_id"] for m in active_matters]
        title_map = {m["matter_id"]: m["title"] for m in active_matters}

        # Step 2: Run queries in parallel
        docs_task = asyncio.to_thread(
            lambda: supabase.table("documents")
            .select("matter_id, page_count")
            .in_("matter_id", matter_ids)
            .execute()
        )

        queries_task = asyncio.to_thread(
            lambda: supabase.table("matter_query_history")
            .select("matter_id", count="exact")
            .in_("matter_id", matter_ids)
            .execute()
        )

        # Also get per-matter query counts
        query_per_matter_task = asyncio.to_thread(
            lambda: supabase.rpc(
                "count_queries_per_matter",
                {"p_matter_ids": matter_ids},
            ).execute()
        )

        docs_result, queries_result, query_per_matter_result = await asyncio.gather(
            docs_task,
            queries_task,
            query_per_matter_task,
            return_exceptions=True,
        )

        # Process document counts and page counts per matter
        doc_counts: dict[str, int] = {}
        page_counts: dict[str, int] = {}

        if not isinstance(docs_result, Exception) and docs_result.data:
            for doc in docs_result.data:
                mid = doc.get("matter_id")
                if mid:
                    doc_counts[mid] = doc_counts.get(mid, 0) + 1
                    page_counts[mid] = page_counts.get(mid, 0) + (
                        doc.get("page_count") or 0
                    )

        # Process query counts
        total_queries = 0
        if not isinstance(queries_result, Exception):
            total_queries = queries_result.count or 0

        query_counts: dict[str, int] = {}
        if (
            not isinstance(query_per_matter_result, Exception)
            and query_per_matter_result.data
        ):
            for row in query_per_matter_result.data:
                query_counts[row["matter_id"]] = row["query_count"]
        else:
            # Fallback: if RPC doesn't exist, divide evenly or set 0
            logger.debug(
                "count_queries_per_matter_rpc_unavailable", fallback="zero_per_matter"
            )

        # Build per-matter stats
        matter_stats = []
        for mid in matter_ids:
            matter_stats.append(
                MatterUsageStats(
                    matter_id=mid,
                    matter_title=title_map.get(mid, "Untitled"),
                    documents=doc_counts.get(mid, 0),
                    pages=page_counts.get(mid, 0),
                    queries=query_counts.get(mid, 0),
                )
            )

        # Sort by pages descending (most active first)
        matter_stats.sort(key=lambda m: m.pages, reverse=True)

        summary = UsageSummary(
            total_documents=sum(doc_counts.values()),
            total_pages=sum(page_counts.values()),
            total_queries=total_queries,
            total_matters=len(matter_ids),
            matters=matter_stats,
        )

        logger.debug(
            "usage_summary_computed",
            user_id=current_user.id,
            total_matters=len(matter_ids),
            total_documents=summary.total_documents,
            total_pages=summary.total_pages,
            total_queries=summary.total_queries,
        )

        return UsageSummaryResponse(data=summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "usage_summary_failed",
            user_id=current_user.id,
            error=str(e),
        )
        # Return empty data on error (graceful degradation)
        return UsageSummaryResponse(data=UsageSummary())
