"""Celery tasks for LLM quota monitoring and alerting.

Story gap-5.2: LLM Quota Monitoring Dashboard

Provides periodic tasks for:
- Checking LLM quota thresholds
- Triggering alerts when usage exceeds configured thresholds
- Logging structured alerts to Axiom via structlog
"""

import structlog

from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.quota_monitoring_tasks.check_llm_quotas",
    bind=True,
    max_retries=1,  # Only retry once - alerting is best-effort
    default_retry_delay=60,  # Wait 1 minute before retry
    soft_time_limit=60,  # 1 minute soft limit
    time_limit=120,  # 2 minute hard limit
)
def check_llm_quotas(self) -> dict:
    """Check LLM quota thresholds and trigger alerts if exceeded.

    Story gap-5.2: AC #2 - Background task for quota alerting.

    This task runs every 5 minutes via Celery Beat and:
    1. Queries current usage from llm_costs table
    2. Compares against limits from llm_quota_limits table
    3. Logs structured alerts when thresholds are breached
    4. Creates in-app notifications for admin users

    Returns:
        Dictionary with check results and alert status.

    Raises:
        Exception: F11 fix - Re-raises exceptions so Celery can track failures.
    """
    import asyncio

    logger.info("llm_quota_check_started", task_id=self.request.id)

    try:
        # F4 fix: Use asyncio.run() instead of manual event loop management
        # This properly handles loop creation/cleanup and is the recommended approach
        result = asyncio.run(_check_quotas_async())
        return result

    except Exception as e:
        logger.error(
            "llm_quota_check_failed",
            task_id=self.request.id,
            error=str(e),
            error_type=type(e).__name__,
        )
        # F11 fix: Re-raise so Celery marks task as failed and can track failure metrics
        raise


async def _check_quotas_async() -> dict:
    """Async implementation of quota checking.

    Returns:
        Dictionary with check results.
    """
    from app.core.cost_tracking import QuotaMonitoringService
    from app.services.supabase.client import get_service_client

    supabase = get_service_client()
    service = QuotaMonitoringService(supabase)

    # Get all provider quotas
    provider_quotas = await service.get_all_provider_quotas()

    alerts_triggered = []
    for pq in provider_quotas:
        if pq.alert_triggered:
            # Log structured alert (sent to Axiom)
            _log_quota_alert(pq)
            alerts_triggered.append(pq.provider)

            # Create in-app notification for admin users
            await _create_admin_notification(pq, supabase)

    result = {
        "status": "success",
        "providers_checked": len(provider_quotas),
        "alerts_triggered": len(alerts_triggered),
        "alert_providers": alerts_triggered,
    }

    logger.info(
        "llm_quota_check_completed",
        **result,
    )

    return result


def _log_quota_alert(pq) -> None:
    """Log a structured quota alert to Axiom.

    Args:
        pq: ProviderQuotaInfo instance.
    """
    logger.warning(
        "llm_quota_alert_triggered",
        event_type="quota_threshold_breach",
        provider=pq.provider,
        daily_tokens_used=pq.daily_tokens_used,
        daily_token_limit=pq.daily_token_limit,
        token_usage_pct=round(pq.token_usage_pct, 1),
        daily_cost_inr=round(pq.daily_cost_inr, 2),
        daily_cost_limit_inr=pq.daily_cost_limit_inr,
        cost_usage_pct=round(pq.cost_usage_pct, 1),
        alert_threshold_pct=pq.alert_threshold_pct,
        projected_exhaustion=pq.projected_exhaustion,
        trend=pq.trend,
        severity="warning" if pq.token_usage_pct < 95 else "critical",
    )


def _sanitize_provider_name(provider: str) -> str:
    """F8 fix: Sanitize provider name to prevent SQL injection in ILIKE.

    Only allows alphanumeric characters and underscores.

    Args:
        provider: Raw provider name.

    Returns:
        Sanitized provider name safe for SQL queries.
    """
    import re
    # Only allow alphanumeric and underscore
    return re.sub(r'[^a-zA-Z0-9_]', '', provider)


async def _create_admin_notification(pq, supabase) -> None:
    """Create in-app notification for admin users about quota breach.

    Args:
        pq: ProviderQuotaInfo instance.
        supabase: Supabase client.
    """
    try:
        from datetime import datetime, timedelta, timezone

        from app.core.config import get_settings
        from app.models.notification import NotificationPriorityEnum, NotificationTypeEnum
        from app.services.notification_service import NotificationService

        settings = get_settings()

        # Get admin emails from config
        admin_emails = (
            settings.admin_emails.split(",")
            if hasattr(settings, "admin_emails") and settings.admin_emails
            else []
        )
        admin_emails = [e.strip().lower() for e in admin_emails if e.strip()]

        if not admin_emails:
            logger.debug("no_admin_emails_configured_for_quota_alert")
            return

        # Get admin user IDs from emails
        result = (
            supabase.table("users")
            .select("id, email")
            .in_("email", admin_emails)
            .execute()
        )

        if not result.data:
            logger.debug("no_admin_users_found_for_quota_alert")
            return

        # Create notification service
        notification_service = NotificationService(supabase)

        # Determine severity
        usage_pct = max(pq.token_usage_pct, pq.cost_usage_pct)
        is_critical = usage_pct >= 95
        priority = NotificationPriorityEnum.HIGH if is_critical else NotificationPriorityEnum.MEDIUM

        # F8 fix: Sanitize provider name for safe use in queries
        safe_provider = _sanitize_provider_name(pq.provider)

        # F12 fix: Use structured alert key prefix for reliable deduplication
        alert_key = f"llm_quota_alert_{safe_provider}"
        title = f"LLM Quota Alert: {safe_provider.title()} at {usage_pct:.0f}%"
        message = (
            f"{safe_provider.title()} API usage has reached {usage_pct:.0f}% of daily limit. "
            f"Tokens: {pq.daily_tokens_used:,} / {pq.daily_token_limit or 'unlimited':,}. "
            f"Cost: ₹{pq.daily_cost_inr:.2f}"
        )
        if pq.projected_exhaustion:
            message += f". Projected exhaustion: {pq.projected_exhaustion}"

        # Check for recent identical notification to avoid spam
        # Only create notification if no similar one in last 30 minutes
        recent_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()

        for admin_user in result.data:
            # F8/F12 fix: Use exact match on alert_key prefix instead of ILIKE
            # This is both safer and more reliable than pattern matching on title
            recent_check = (
                supabase.table("notifications")
                .select("id")
                .eq("user_id", admin_user["id"])
                .like("title", f"LLM Quota Alert: {safe_provider.title()}%")
                .gte("created_at", recent_cutoff)
                .limit(1)
                .execute()
            )

            if recent_check.data:
                logger.debug(
                    "quota_alert_notification_skipped_recent",
                    admin_email=admin_user["email"],
                    provider=safe_provider,
                )
                continue

            # Create notification
            await notification_service.create_notification(
                user_id=admin_user["id"],
                type=NotificationTypeEnum.WARNING,
                title=title,
                message=message,
                priority=priority,
            )

            logger.info(
                "quota_alert_notification_created",
                admin_email=admin_user["email"],
                provider=safe_provider,
                usage_pct=usage_pct,
            )

    except Exception as e:
        logger.warning(
            "quota_alert_notification_failed",
            provider=pq.provider,
            error=str(e),
        )
