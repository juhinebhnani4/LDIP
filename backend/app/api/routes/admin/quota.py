"""Admin LLM Quota Monitoring API routes.

Story gap-5.2: LLM Quota Monitoring Dashboard

Provides admin-only endpoints for:
- GET /api/admin/llm-quota - Get current LLM quota status and usage

All endpoints require admin access (configured via ADMIN_EMAILS env var).
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_user, require_admin_access
from app.core.config import get_settings
from app.core.cost_tracking import (
    USD_TO_INR_RATE,
    QuotaMonitoringService,
)
from app.core.rate_limit import ADMIN_RATE_LIMIT, STANDARD_RATE_LIMIT, limiter
from app.models.auth import AuthenticatedUser
from app.models.quota import LLMQuotaData, LLMQuotaResponse, ProviderQuota
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
