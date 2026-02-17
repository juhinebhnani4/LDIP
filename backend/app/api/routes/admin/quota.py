"""Admin Monitoring API routes.

Story gap-5.2: LLM Quota Monitoring Dashboard
Story 5.6: Queue Depth Visibility Dashboard

Provides admin-only endpoints for:
- GET /api/admin/llm-quota - Get current LLM quota status and usage
- GET /api/admin/queue-status - Get Celery queue depths and metrics
- GET /api/admin/queue-status/health - Health check for queue monitoring

All endpoints require admin access (configured via ADMIN_EMAILS env var).
"""

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from postgrest.exceptions import APIError as PostgrestAPIError

from app.api.deps import get_current_user, require_admin_access
from app.core.config import get_settings
from app.core.cost_tracking import (
    USD_TO_INR_RATE,
    QuotaMonitoringService,
)
from app.core.rate_limit import ADMIN_RATE_LIMIT, STANDARD_RATE_LIMIT, limiter
from app.models.auth import AuthenticatedUser
from app.models.cost import (
    DailyUsage,
    MatterUsage,
    MonthlyCostReport,
    MonthlyCostReportResponse,
    OperationUsage,
    PracticeGroupCost,
    ProviderUsage,
    UsageDashboardResponse,
)
from app.models.quota import LLMQuotaData, LLMQuotaResponse, ProviderQuota
from app.models.queue_status import (
    QueueHealthResponse,
    QueueMetrics,
    QueueStatusData,
    QueueStatusResponse,
)
from app.services.queue_metrics_service import (
    DEFAULT_ALERT_THRESHOLD,
    get_queue_metrics_service,
)
from app.services.matter_cost_service import normalize_operation
from app.services.supabase.client import get_service_client

router = APIRouter(prefix="/admin", tags=["admin-quota"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Admin Status Check (F1, F2, F3 fix)
# =============================================================================


@router.get(
    "/status",
    summary="Check Admin Status",
    description="Check if the current user has admin privileges.",
)
@limiter.limit(STANDARD_RATE_LIMIT)
async def check_admin_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Check if current user is an admin.

    This endpoint allows the frontend to check admin status at runtime
    instead of relying on build-time environment variables.

    Returns:
        {"isAdmin": bool, "email": str}
    """
    settings = get_settings()
    admin_emails = [
        e.strip().lower()
        for e in (settings.admin_emails or "").split(",")
        if e.strip()
    ]
    user_email = (current_user.email or "").lower()
    is_admin = user_email in admin_emails

    logger.debug(
        "admin_status_check",
        user_id=current_user.id,
        email=user_email,
        is_admin=is_admin,
    )

    return {
        "data": {
            "isAdmin": is_admin,
            "email": current_user.email,
        }
    }


@router.get(
    "/llm-quota",
    response_model=LLMQuotaResponse,
    response_model_by_alias=True,
    summary="Get LLM Quota Status",
    description="""
    Get current LLM API usage and quota status for all providers.

    Returns:
    - Usage vs limits for OpenAI and Gemini
    - Current RPM and rate limiter status
    - Projected exhaustion date based on 7-day rolling average
    - Alert status (triggered if usage >= 80% of limit)

    **Requires admin access.**
    """,
    responses={
        200: {
            "description": "Quota status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "providers": [
                                {
                                    "provider": "gemini",
                                    "currentRpm": 15,
                                    "rpmLimit": 60,
                                    "rpmUsagePct": 25.0,
                                    "dailyTokensUsed": 500000,
                                    "dailyTokenLimit": 1000000,
                                    "dailyCostInr": 250.50,
                                    "dailyCostLimitInr": 500.00,
                                    "rateLimitedCount": 0,
                                    "projectedExhaustion": "2026-02-15",
                                    "trend": "stable",
                                    "alertTriggered": False,
                                }
                            ],
                            "lastUpdated": "2026-01-27T10:30:00Z",
                            "alertThresholdPct": 80,
                            "usdToInrRate": 83.50,
                        }
                    }
                }
            },
        },
        403: {
            "description": "Admin access required",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "ADMIN_REQUIRED",
                            "message": "Admin access required for this operation",
                            "details": {},
                        }
                    }
                }
            },
        },
    },
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_llm_quota(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> LLMQuotaResponse:
    """Get LLM quota status for all providers.

    Story gap-5.2: AC #1 - GET /api/admin/llm-quota endpoint.

    Args:
        request: FastAPI request for rate limiting binding.
        admin: Authenticated admin user.

    Returns:
        LLMQuotaResponse with provider quota data.

    Raises:
        HTTPException: On authentication or query errors.
    """
    try:
        logger.info(
            "admin_llm_quota_request",
            admin_id=admin.id,
            admin_email=admin.email,
        )

        # Get service client for database access
        # F5 fix: Always create fresh service instance to avoid stale client references
        supabase = get_service_client()
        service = QuotaMonitoringService(supabase)

        # Get all provider quotas
        provider_quotas = await service.get_all_provider_quotas()

        # Convert to response models
        providers = [
            ProviderQuota(
                provider=pq.provider,
                currentRpm=pq.current_rpm,
                rpmLimit=pq.rpm_limit,
                rpmUsagePct=round(pq.rpm_usage_pct, 1),
                dailyTokensUsed=pq.daily_tokens_used,
                dailyTokenLimit=pq.daily_token_limit,
                dailyCostInr=round(pq.daily_cost_inr, 2),
                dailyCostLimitInr=pq.daily_cost_limit_inr,
                rateLimitedCount=pq.rate_limited_count,
                projectedExhaustion=pq.projected_exhaustion,
                trend=pq.trend,
                alertTriggered=pq.alert_triggered,
            )
            for pq in provider_quotas
        ]

        # Check if any alerts triggered
        alerts_triggered = sum(1 for p in providers if p.alert_triggered)
        if alerts_triggered > 0:
            logger.warning(
                "llm_quota_alerts_active",
                admin_id=admin.id,
                alerts_count=alerts_triggered,
                providers=[p.provider for p in providers if p.alert_triggered],
            )

        data = LLMQuotaData(
            providers=providers,
            lastUpdated=datetime.now(timezone.utc).isoformat(),
            alertThresholdPct=80,
            usdToInrRate=USD_TO_INR_RATE,
        )

        return LLMQuotaResponse(data=data)

    except Exception as e:
        logger.error(
            "admin_llm_quota_failed",
            admin_id=admin.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "QUOTA_QUERY_FAILED",
                    "message": "Failed to retrieve LLM quota status",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Queue Status Monitoring (Story 5.6)
# =============================================================================


@router.get(
    "/queue-status",
    response_model=QueueStatusResponse,
    response_model_by_alias=True,
    summary="Get Queue Status",
    description="""
    Get current Celery queue depths and metrics for all queues.

    Returns:
    - Pending, active, and failed job counts for each queue (default, high, low)
    - Total pending and active jobs across all queues
    - Active worker count
    - Alert status (triggered if any queue exceeds threshold)
    - Timestamp of when metrics were collected

    **Requires admin access.**
    """,
    responses={
        200: {
            "description": "Queue status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "queues": [
                                {
                                    "queueName": "default",
                                    "pendingCount": 25,
                                    "activeCount": 5,
                                    "failedCount": 2,
                                    "completed24h": 150,
                                    "avgProcessingTimeMs": 45000,
                                    "trend": "stable",
                                    "alertTriggered": False,
                                }
                            ],
                            "totalPending": 30,
                            "totalActive": 8,
                            "activeWorkers": 3,
                            "lastCheckedAt": "2026-01-27T10:30:00Z",
                            "alertThreshold": 100,
                            "isHealthy": True,
                        }
                    }
                }
            },
        },
        403: {
            "description": "Admin access required",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "ADMIN_REQUIRED",
                            "message": "Admin access required for this operation",
                            "details": {},
                        }
                    }
                }
            },
        },
    },
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_queue_status(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> QueueStatusResponse:
    """Get Celery queue status for all queues.

    Story 5.6: AC #1 - GET /api/admin/queue-status endpoint.

    Args:
        request: FastAPI request for rate limiting binding.
        admin: Authenticated admin user.

    Returns:
        QueueStatusResponse with queue metrics data.

    Raises:
        HTTPException: On authentication or query errors.
    """
    try:
        logger.info(
            "admin_queue_status_request",
            admin_id=admin.id,
            admin_email=admin.email,
        )

        service = get_queue_metrics_service()

        # Get metrics for all queues
        queue_metrics_list = await service.get_all_queue_metrics()

        # Get active worker count
        active_workers = await service.get_active_worker_count()

        # Convert to response models
        queues = [
            QueueMetrics(
                queueName=qm.queue_name,
                pendingCount=qm.pending_count,
                activeCount=qm.active_count,
                failedCount=qm.failed_count,
                completed24h=qm.completed_24h,
                avgProcessingTimeMs=qm.avg_processing_time_ms,
                trend=qm.trend,
                alertTriggered=qm.alert_triggered,
            )
            for qm in queue_metrics_list
        ]

        # Calculate totals
        total_pending = sum(q.pending_count for q in queues)
        total_active = sum(q.active_count for q in queues)
        is_healthy = not any(q.alert_triggered for q in queues)

        # Log alerts if any
        alert_queues = [q.queue_name for q in queues if q.alert_triggered]
        if alert_queues:
            logger.warning(
                "queue_alerts_active",
                admin_id=admin.id,
                alert_queues=alert_queues,
                total_pending=total_pending,
            )

        data = QueueStatusData(
            queues=queues,
            totalPending=total_pending,
            totalActive=total_active,
            activeWorkers=active_workers,
            lastCheckedAt=datetime.now(timezone.utc).isoformat(),
            alertThreshold=DEFAULT_ALERT_THRESHOLD,
            isHealthy=is_healthy,
        )

        return QueueStatusResponse(data=data)

    except Exception as e:
        logger.error(
            "admin_queue_status_failed",
            admin_id=admin.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "QUEUE_STATUS_FAILED",
                    "message": "Failed to retrieve queue status",
                    "details": {},
                }
            },
        ) from e


@router.get(
    "/queue-status/health",
    response_model=QueueHealthResponse,
    response_model_by_alias=True,
    summary="Queue Health Check",
    description="""
    Health check endpoint for queue monitoring system.

    Returns:
    - Redis connection status
    - Active worker count
    - Timestamp of check
    - Overall health status (healthy, degraded, unhealthy)

    Pre-mortem fix: Use this to detect stale metrics (>60s warning).

    **Requires admin access.**
    """,
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_queue_health(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> QueueHealthResponse:
    """Check queue monitoring system health.

    Story 5.6: Pre-mortem fix - Health check for staleness detection.

    Args:
        request: FastAPI request for rate limiting binding.
        admin: Authenticated admin user.

    Returns:
        QueueHealthResponse with health status.
    """
    try:
        service = get_queue_metrics_service()
        health_data = await service.check_health()

        logger.debug(
            "admin_queue_health_check",
            admin_id=admin.id,
            status=health_data.get("status"),
        )

        return QueueHealthResponse(data=health_data)

    except Exception as e:
        logger.error(
            "admin_queue_health_failed",
            admin_id=admin.id,
            error=str(e),
        )
        # Return unhealthy status on error instead of raising
        return QueueHealthResponse(
            data={
                "status": "unhealthy",
                "redisConnected": False,
                "workerCount": 0,
                "lastCheckedAt": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }
        )


# =============================================================================
# Monthly Cost Reports (Story 7.2)
# =============================================================================


@router.get(
    "/cost-report",
    response_model=MonthlyCostReportResponse,
    response_model_by_alias=True,
    summary="Get Monthly Cost Report",
    description="""
    Get monthly cost report broken down by practice group.

    Returns:
    - Total cost across all practice groups
    - Matter count, document count, and cost per practice group
    - Exportable data for CSV/PDF generation

    **Requires admin access.**
    """,
    responses={
        200: {
            "description": "Cost report retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "reportMonth": "2026-01",
                            "generatedAt": "2026-01-27T10:30:00Z",
                            "totalCostInr": 25000.50,
                            "totalCostUsd": 299.41,
                            "practiceGroups": [
                                {
                                    "practiceGroup": "Litigation",
                                    "matterCount": 12,
                                    "documentCount": 150,
                                    "totalCostInr": 15000.00,
                                    "totalCostUsd": 179.64,
                                },
                            ],
                        }
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
async def get_monthly_cost_report(
    request: Request,
    year: int | None = Query(default=None, ge=2020, le=2100, description="Report year"),
    month: int | None = Query(default=None, ge=1, le=12, description="Report month (1-12)"),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> MonthlyCostReportResponse:
    """Get monthly cost report by practice group.

    Story 7.2: Monthly Cost Report by Practice Group

    AC:
    - Report showing costs by practice group
    - Includes: matter count, document count, total cost per group
    - Exportable as CSV or PDF

    Args:
        request: FastAPI request for rate limiting binding.
        year: Report year (2020-2100, defaults to current year).
        month: Report month (1-12, defaults to current month).
        admin: Authenticated admin user.

    Returns:
        MonthlyCostReportResponse with practice group breakdown.
    """
    # Default to current month
    now = datetime.now(timezone.utc)
    report_year = year if year else now.year
    report_month = month if month else now.month

    logger.info(
        "admin_cost_report_request",
        admin_id=admin.id,
        admin_email=admin.email,
        year=report_year,
        month=report_month,
    )

    try:
        # Get service client
        supabase = get_service_client()

        # Call the RPC function for aggregated data
        result = supabase.rpc(
            "get_monthly_cost_report",
            {"p_year": report_year, "p_month": report_month},
        ).execute()

        # Build practice group list
        practice_groups = []
        total_cost_inr = 0.0
        total_cost_usd = 0.0

        for row in result.data or []:
            cost_inr = float(row.get("total_cost_inr") or 0)
            cost_usd = float(row.get("total_cost_usd") or 0)
            total_cost_inr += cost_inr
            total_cost_usd += cost_usd

            practice_groups.append(
                PracticeGroupCost(
                    practice_group=row.get("practice_group", "Unassigned"),
                    matter_count=row.get("matter_count", 0),
                    document_count=row.get("document_count", 0),
                    total_cost_inr=round(cost_inr, 2),
                    total_cost_usd=round(cost_usd, 6),
                )
            )

        report = MonthlyCostReport(
            report_month=f"{report_year}-{report_month:02d}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_cost_inr=round(total_cost_inr, 2),
            total_cost_usd=round(total_cost_usd, 6),
            practice_groups=practice_groups,
        )

        logger.info(
            "admin_cost_report_generated",
            admin_id=admin.id,
            total_cost_inr=report.total_cost_inr,
            practice_group_count=len(practice_groups),
        )

        return MonthlyCostReportResponse(data=report)

    except PostgrestAPIError as e:
        # Database/RPC errors
        logger.error(
            "admin_cost_report_failed",
            admin_id=admin.id,
            error=str(e),
            error_type="database",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "COST_REPORT_FAILED",
                    "message": "Failed to generate cost report",
                    "details": {},
                }
            },
        ) from e
    except ValueError as e:
        # Data parsing errors
        logger.error(
            "admin_cost_report_parse_failed",
            admin_id=admin.id,
            error=str(e),
            error_type="parse",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "COST_REPORT_PARSE_FAILED",
                    "message": "Failed to parse cost report data",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Usage Dashboard (Full Cost Tracking)
# =============================================================================


@router.get(
    "/usage",
    response_model=UsageDashboardResponse,
    response_model_by_alias=True,
    summary="Get Usage Dashboard Data",
    description="""
    Get full usage dashboard data for a given month.

    Returns:
    - Total spend in USD and INR
    - Budget utilization
    - Daily spend time-series
    - Breakdown by provider, operation, and matter

    **Requires admin access.**
    """,
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_usage_dashboard(
    request: Request,
    year: int | None = Query(default=None, ge=2020, le=2100, description="Year"),
    month: int | None = Query(default=None, ge=1, le=12, description="Month (1-12)"),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> UsageDashboardResponse:
    """Get usage dashboard data for a month.

    Queries llm_costs table and aggregates by day, provider, operation, matter.
    """
    now = datetime.now(timezone.utc)
    q_year = year if year else now.year
    q_month = month if month else now.month

    logger.info(
        "admin_usage_dashboard_request",
        admin_id=admin.id,
        year=q_year,
        month=q_month,
    )

    try:
        supabase = get_service_client()
        settings = get_settings()

        # Build date range for the month
        month_start = datetime(q_year, q_month, 1, tzinfo=timezone.utc)
        if q_month == 12:
            month_end = datetime(q_year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            month_end = datetime(q_year, q_month + 1, 1, tzinfo=timezone.utc)

        # Fetch all cost records for the month (paginate past Supabase 1000-row default)
        rows: list[dict] = []
        page_size = 1000
        offset = 0
        while True:
            result = (
                supabase.table("llm_costs")
                .select(
                    "provider, operation, matter_id, input_tokens, output_tokens, "
                    "total_cost_usd, total_cost_inr, created_at"
                )
                .gte("created_at", month_start.isoformat())
                .lt("created_at", month_end.isoformat())
                .order("created_at")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page = result.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size

        # Aggregate totals
        total_usd = 0.0
        total_inr = 0.0
        total_tokens = 0
        total_requests = len(rows)

        # Group by day
        daily_map: dict[str, dict] = {}
        # Group by provider
        provider_map: dict[str, dict] = {}
        # Group by operation
        operation_map: dict[str, dict] = {}
        # Group by matter
        matter_map: dict[str, dict] = {}

        for row in rows:
            cost_usd = float(row.get("total_cost_usd") or 0)
            cost_inr = float(row.get("total_cost_inr") or 0)
            inp = int(row.get("input_tokens") or 0)
            out = int(row.get("output_tokens") or 0)
            tokens = inp + out

            total_usd += cost_usd
            total_inr += cost_inr
            total_tokens += tokens

            # Daily
            created = row.get("created_at", "")
            day_key = created[:10] if created else "unknown"
            if day_key not in daily_map:
                daily_map[day_key] = {"usd": 0.0, "inr": 0.0, "requests": 0, "tokens": 0}
            daily_map[day_key]["usd"] += cost_usd
            daily_map[day_key]["inr"] += cost_inr
            daily_map[day_key]["requests"] += 1
            daily_map[day_key]["tokens"] += tokens

            # Provider
            provider = row.get("provider", "unknown")
            if provider not in provider_map:
                provider_map[provider] = {"usd": 0.0, "inr": 0.0, "requests": 0, "inp": 0, "out": 0}
            provider_map[provider]["usd"] += cost_usd
            provider_map[provider]["inr"] += cost_inr
            provider_map[provider]["requests"] += 1
            provider_map[provider]["inp"] += inp
            provider_map[provider]["out"] += out

            # Operation (normalize to grouped categories)
            operation = normalize_operation(row.get("operation", "unknown"))
            if operation not in operation_map:
                operation_map[operation] = {"usd": 0.0, "inr": 0.0, "requests": 0, "inp": 0, "out": 0}
            operation_map[operation]["usd"] += cost_usd
            operation_map[operation]["inr"] += cost_inr
            operation_map[operation]["requests"] += 1
            operation_map[operation]["inp"] += inp
            operation_map[operation]["out"] += out

            # Matter
            matter_id = row.get("matter_id")
            if matter_id:
                if matter_id not in matter_map:
                    matter_map[matter_id] = {"usd": 0.0, "inr": 0.0, "requests": 0}
                matter_map[matter_id]["usd"] += cost_usd
                matter_map[matter_id]["inr"] += cost_inr
                matter_map[matter_id]["requests"] += 1

        # Build response
        daily_spend = sorted(
            [
                DailyUsage(
                    date=k,
                    spendUsd=round(v["usd"], 6),
                    spendInr=round(v["inr"], 2),
                    requests=v["requests"],
                    tokens=v["tokens"],
                )
                for k, v in daily_map.items()
            ],
            key=lambda d: d.date,
        )

        by_provider = sorted(
            [
                ProviderUsage(
                    provider=k,
                    spendUsd=round(v["usd"], 6),
                    spendInr=round(v["inr"], 2),
                    requests=v["requests"],
                    inputTokens=v["inp"],
                    outputTokens=v["out"],
                )
                for k, v in provider_map.items()
            ],
            key=lambda p: p.spend_usd,
            reverse=True,
        )

        by_operation = sorted(
            [
                OperationUsage(
                    operation=k,
                    spendUsd=round(v["usd"], 6),
                    spendInr=round(v["inr"], 2),
                    requests=v["requests"],
                    inputTokens=v["inp"],
                    outputTokens=v["out"],
                )
                for k, v in operation_map.items()
            ],
            key=lambda o: o.spend_usd,
            reverse=True,
        )

        by_matter = sorted(
            [
                MatterUsage(
                    matterId=k,
                    spendUsd=round(v["usd"], 6),
                    spendInr=round(v["inr"], 2),
                    requests=v["requests"],
                )
                for k, v in matter_map.items()
            ],
            key=lambda m: m.spend_usd,
            reverse=True,
        )[:20]  # Top 20 matters

        return UsageDashboardResponse(
            month=f"{q_year}-{q_month:02d}",
            totalSpendUsd=round(total_usd, 6),
            totalSpendInr=round(total_inr, 2),
            budgetUsd=settings.monthly_cost_budget_usd,
            totalTokens=total_tokens,
            totalRequests=total_requests,
            dailySpend=daily_spend,
            byProvider=by_provider,
            byOperation=by_operation,
            byMatter=by_matter,
        )

    except Exception as e:
        logger.error(
            "admin_usage_dashboard_failed",
            admin_id=admin.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "USAGE_DASHBOARD_FAILED",
                    "message": "Failed to retrieve usage dashboard data",
                    "details": {},
                }
            },
        ) from e
