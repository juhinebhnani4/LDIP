"""Admin Monitoring API routes.

Gap 7: Vector Quantization — Chunk Count Monitoring Dashboard
Gap 8: HNSW Index Tuning — Index Configuration Visibility
Gap 9: Automated RAGAS Regression — Quality Monitoring Dashboard

Provides admin-only endpoints for:
- GET /api/admin/chunk-metrics - Per-matter and global chunk count metrics
- GET /api/admin/quality-metrics - RAG quality monitoring with regression alerts

All endpoints require admin access (configured via ADMIN_EMAILS env var).
"""

import asyncio
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import require_admin_access
from app.core.rate_limit import ADMIN_RATE_LIMIT, limiter
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_service_client

router = APIRouter(prefix="/admin", tags=["admin-monitoring"])
logger = structlog.get_logger(__name__)

# =============================================================================
# Gap 7: Chunk Metrics Monitoring
# =============================================================================

# Thresholds for alerting — revisit quantization when exceeded
MATTER_CHUNK_THRESHOLD = 50_000   # Per-matter: 50K chunks
GLOBAL_CHUNK_THRESHOLD = 500_000  # Global: 500K chunks


@router.get(
    "/chunk-metrics",
    summary="Get Chunk Count Metrics",
    description="""
    Get chunk count metrics for vector quantization monitoring.

    Returns:
    - Per-matter chunk counts (parent, child, table breakdown)
    - Global totals (total chunks, embedding coverage)
    - Alert flags when thresholds are exceeded
    - HNSW index configuration info

    Thresholds:
    - Per-matter: 50K chunks (single matter becoming too large for HNSW)
    - Global: 500K chunks (total storage/memory concern)

    When thresholds are exceeded, consider:
    1. halfvec (float16) — 2x compression, ~2-3% accuracy loss
    2. Dimension reduction — PCA to 768 dims
    3. Scalar quantization (int8) — 4x compression

    **Requires admin access.**
    """,
    responses={
        200: {
            "description": "Chunk metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "global": {
                            "totalChunks": 15000,
                            "totalWithEmbedding": 14500,
                            "totalWithVoyage": 12000,
                            "totalMatters": 5,
                            "exceedsGlobalThreshold": False,
                            "globalThreshold": 500000,
                        },
                        "matters": [
                            {
                                "matterId": "uuid-here",
                                "matterTitle": "Smith v Jones",
                                "totalChunks": 5000,
                                "parentChunks": 800,
                                "childChunks": 4000,
                                "tableChunks": 200,
                                "hasVoyageEmbeddings": 4500,
                                "exceedsThreshold": False,
                            }
                        ],
                        "thresholds": {
                            "perMatter": 50000,
                            "global": 500000,
                        },
                        "indexConfig": {
                            "m": 16,
                            "efConstruction": 128,
                            "efSearch": 80,
                            "vectorDimensions": {
                                "openai": 1536,
                                "voyage": 1024,
                            },
                            "quantization": "float32",
                            "recommendation": "No action needed at current scale",
                        },
                        "alertsTriggered": False,
                        "lastUpdated": "2026-02-20T10:30:00Z",
                    }
                }
            },
        },
        403: {
            "description": "Admin access required",
        },
    },
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_chunk_metrics(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> dict:
    """Get chunk count metrics for monitoring.

    Gap 7: Vector Quantization — Monitoring Dashboard

    Calls two Supabase RPC functions:
    - get_chunk_metrics() — per-matter breakdown
    - get_global_chunk_count() — global totals

    Returns combined metrics with alert flags and HNSW config info.
    """
    try:
        logger.info(
            "admin_chunk_metrics_request",
            admin_id=admin.id,
            admin_email=admin.email,
        )

        supabase = get_service_client()

        # Fetch per-matter and global metrics in parallel
        matter_result, global_result = await asyncio.gather(
            asyncio.to_thread(
                lambda: supabase.rpc("get_chunk_metrics").execute()
            ),
            asyncio.to_thread(
                lambda: supabase.rpc("get_global_chunk_count").execute()
            ),
        )

        # Parse per-matter metrics
        matters = []
        any_matter_alert = False
        for row in matter_result.data or []:
            total = int(row.get("total_chunks") or 0)
            exceeds = total > MATTER_CHUNK_THRESHOLD
            if exceeds:
                any_matter_alert = True

            matters.append({
                "matterId": row.get("matter_id"),
                "matterTitle": row.get("matter_title", "Untitled"),
                "totalChunks": total,
                "parentChunks": int(row.get("parent_chunks") or 0),
                "childChunks": int(row.get("child_chunks") or 0),
                "tableChunks": int(row.get("table_chunks") or 0),
                "hasVoyageEmbeddings": int(row.get("has_voyage_embeddings") or 0),
                "exceedsThreshold": exceeds,
            })

        # Parse global metrics
        global_row = (global_result.data or [{}])[0] if global_result.data else {}
        global_total = int(global_row.get("total_chunks") or 0)
        global_exceeds = global_total > GLOBAL_CHUNK_THRESHOLD

        global_data = {
            "totalChunks": global_total,
            "totalWithEmbedding": int(global_row.get("total_with_embedding") or 0),
            "totalWithVoyage": int(global_row.get("total_with_voyage") or 0),
            "totalMatters": int(global_row.get("total_matters") or 0),
            "exceedsGlobalThreshold": global_exceeds,
            "globalThreshold": GLOBAL_CHUNK_THRESHOLD,
        }

        # Determine recommendation based on scale
        alerts_triggered = any_matter_alert or global_exceeds
        recommendation = _get_quantization_recommendation(
            global_total, any_matter_alert, global_exceeds
        )

        # Log alerts
        if alerts_triggered:
            alert_matters = [m["matterTitle"] for m in matters if m["exceedsThreshold"]]
            logger.warning(
                "chunk_metrics_threshold_exceeded",
                admin_id=admin.id,
                global_total=global_total,
                global_exceeds=global_exceeds,
                alert_matters=alert_matters,
            )

        return {
            "global": global_data,
            "matters": matters,
            "thresholds": {
                "perMatter": MATTER_CHUNK_THRESHOLD,
                "global": GLOBAL_CHUNK_THRESHOLD,
            },
            # NOTE: These values must match the HNSW index parameters in
            # supabase/migrations/20260220400002_tune_hnsw_indexes.sql.
            # Update here if migration params change (m, ef_construction, ef_search).
            # Querying pg_indexes at runtime is possible but adds latency for
            # rarely-changing config — hardcoded is acceptable for a monitoring dashboard.
            "indexConfig": {
                "m": 16,
                "efConstruction": 128,
                "efSearch": 80,
                "vectorDimensions": {
                    "openai": 1536,
                    "voyage": 1024,
                },
                "quantization": "float32 (full precision)",
                "recommendation": recommendation,
            },
            "alertsTriggered": alerts_triggered,
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(
            "admin_chunk_metrics_failed",
            admin_id=admin.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CHUNK_METRICS_FAILED",
                    "message": "Failed to retrieve chunk metrics",
                    "details": {},
                }
            },
        ) from e


def _get_quantization_recommendation(
    global_total: int,
    any_matter_alert: bool,
    global_exceeds: bool,
) -> str:
    """Generate a human-readable recommendation based on chunk counts.

    Progressive recommendations based on scale:
    - <100K: No action needed
    - 100K-500K: Monitor closely
    - >500K (or matter >50K): Consider quantization
    - >1M: Strongly recommend quantization or separate vector DB
    """
    if global_total > 1_000_000:
        return (
            "URGENT: Consider halfvec(float16) for 2x compression with ~3% accuracy loss, "
            "or migrate to a dedicated vector DB (Pinecone/Weaviate) for RLS-free scaling"
        )
    if global_exceeds:
        return (
            "Consider halfvec(float16) — pgvector 0.7+ supports it natively. "
            "2x memory reduction with ~2-3% accuracy loss. "
            "Alternative: PCA dimension reduction to 768 dims."
        )
    if any_matter_alert:
        return (
            "A matter exceeds 50K chunks. Monitor HNSW recall quality for that matter. "
            "If query latency exceeds 200ms, consider per-matter quantization."
        )
    if global_total > 100_000:
        return (
            "Approaching threshold. Monitor query latency and storage costs. "
            "No action needed yet."
        )
    return "No action needed at current scale. float32 is optimal for legal precision."


# =============================================================================
# Gap 9: Quality Metrics Monitoring
# =============================================================================


@router.get(
    "/quality-metrics",
    summary="Get RAG Quality Metrics",
    description="""
    Get RAG quality metrics for evaluation monitoring.

    Returns:
    - Per-matter quality scores (latest batch vs active baseline)
    - Regression alerts (matters where quality dropped > 10%)
    - Evaluation schedule status
    - Monthly evaluation cost estimate
    - Golden dataset coverage

    **Requires admin access.**
    """,
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_quality_metrics(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> dict:
    """Get RAG quality metrics for admin monitoring dashboard.

    Gap 9: Automated RAGAS Regression — Quality Monitoring Dashboard

    Calls the get_evaluation_quality_summary() RPC function which aggregates:
    - Latest batch scores per matter
    - Active baseline comparison
    - Regression flags
    - Evaluation frequency
    """
    try:
        from app.core.config import get_settings

        settings = get_settings()

        logger.info(
            "admin_quality_metrics_request",
            admin_id=admin.id,
            admin_email=admin.email,
        )

        supabase = get_service_client()

        # Fetch quality summary (one RPC call — all aggregation in SQL)
        summary_result = await asyncio.to_thread(
            lambda: supabase.rpc("get_evaluation_quality_summary").execute()
        )

        # Parse per-matter metrics
        matters = []
        regression_count = 0
        total_golden_items = 0

        for row in summary_result.data or []:
            has_regression = bool(row.get("has_regression", False))
            if has_regression:
                regression_count += 1

            golden_count = int(row.get("golden_item_count") or 0)
            total_golden_items += golden_count

            matters.append({
                "matterId": row.get("matter_id"),
                "matterTitle": row.get("matter_title", "Untitled"),
                # Latest batch scores
                "latestOverall": row.get("latest_overall"),
                "latestFaithfulness": row.get("latest_faithfulness"),
                "latestRelevancy": row.get("latest_relevancy"),
                "latestRecall": row.get("latest_recall"),
                "latestEvalDate": row.get("latest_eval_date"),
                "latestJobId": row.get("latest_job_id"),
                "latestEvalCount": int(row.get("latest_eval_count") or 0),
                # Baseline comparison
                "baselineOverall": row.get("baseline_overall"),
                "baselineDate": row.get("baseline_date"),
                "baselineItemCount": int(row.get("baseline_item_count") or 0),
                # Delta and regression
                "overallDelta": row.get("overall_delta"),
                "hasRegression": has_regression,
                # Coverage
                "goldenItemCount": golden_count,
                # Frequency
                "totalEvals30d": int(row.get("total_evals_30d") or 0),
                "lastEvalAgeHours": row.get("last_eval_age_hours"),
            })

        return {
            "matters": matters,
            "summary": {
                "totalMatters": len(matters),
                "mattersWithRegression": regression_count,
                "totalGoldenItems": total_golden_items,
                "mattersWithBaseline": sum(
                    1 for m in matters if m["baselineOverall"] is not None
                ),
                "mattersEvaluatedRecently": sum(
                    1 for m in matters
                    if m.get("lastEvalAgeHours") is not None
                    and m["lastEvalAgeHours"] < 48
                ),
            },
            "schedule": {
                "enabled": settings.evaluation_schedule_enabled,
                "regressionThreshold": settings.evaluation_regression_threshold,
                "criticalThreshold": settings.evaluation_critical_threshold,
                "monthlyBudgetUsd": settings.evaluation_monthly_budget_usd,
                "autoBaseline": settings.evaluation_auto_baseline,
            },
            "hasRegressions": regression_count > 0,
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(
            "admin_quality_metrics_failed",
            admin_id=admin.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "QUALITY_METRICS_FAILED",
                    "message": "Failed to retrieve quality metrics",
                    "details": {},
                }
            },
        ) from e
